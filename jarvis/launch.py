"""Cross-platform launcher for the user's saved backend choice."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

from local_settings import BASE_DIR, CONFIG_PATH, provider
from router_client import RouterClient, RouterClientError


def desktop_environment(backend: str) -> dict:
    environment = dict(os.environ, JARVIS_PROVIDER=backend)
    environment.pop("GROQ_API_KEY", None)
    environment.pop("ROUTER_API_KEY", None)
    environment.pop("JARVIS_ROUTER_API_KEY", None)
    return environment


def launch(mode="--voice") -> int:
    if not CONFIG_PATH.exists() and not os.getenv("JARVIS_PROVIDER"):
        from setup_assistant import run_setup
        if run_setup() or not CONFIG_PATH.exists():
            return 1
    backend = provider()
    environment = desktop_environment(backend)
    if backend == "local":
        return subprocess.call([sys.executable, str(BASE_DIR / "main.py"), mode], env=environment)

    from dotenv import dotenv_values
    router_dir = BASE_DIR.parent / "router"
    values = dotenv_values(router_dir / ".env")
    key = values.get("ROUTER_API_KEY") or ""
    groq_key = values.get("GROQ_API_KEY") or ""
    if not key or key.startswith("replace_with_") or not groq_key.startswith("gsk_"):
        raise RouterClientError("Run Setup_Jarvis and choose Groq API to configure your key.")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    environment.update(JARVIS_ROUTER_URL=url, JARVIS_ROUTER_API_KEY=key)
    router_environment = dict(os.environ, GROQ_API_KEY=groq_key, ROUTER_API_KEY=key)
    process = None
    try:
        with (BASE_DIR / "router.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                cwd=router_dir, env=router_environment, stdout=log, stderr=log,
            )
            client = RouterClient(base_url=url, api_key=key, timeout=1)
            for _ in range(50):
                if process.poll() is not None:
                    raise RouterClientError("The Groq router could not start. Re-run setup; details are in jarvis/router.log.")
                try:
                    if client.health():
                        break
                except RouterClientError:
                    pass
                time.sleep(0.2)
            else:
                raise RouterClientError("The Groq router did not become ready. See jarvis/router.log.")
            return subprocess.call([sys.executable, str(BASE_DIR / "main.py"), mode], env=environment)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in {"--voice", "--text", "--diagnose"} else "--voice"
    try:
        raise SystemExit(launch(mode))
    except (RouterClientError, ImportError, OSError) as exc:
        print(f"JARVIS could not start: {exc}")
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(0)

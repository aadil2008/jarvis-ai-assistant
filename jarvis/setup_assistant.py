"""Choose local or cloud operation explicitly; keep the choice across launches."""
from __future__ import annotations

import getpass
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

from local_settings import BASE_DIR, write_settings
from router_client import RouterClientError

ROUTER_DIR = BASE_DIR.parent / "router"


def install_requirements(path: Path) -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(path)], check=True)


def configure_cloud(*, input_fn=input, password_fn=getpass.getpass, env_path=None) -> bool:
    from dotenv import dotenv_values, set_key
    path = env_path or ROUTER_DIR / ".env"
    values = dotenv_values(path) if path.exists() else {}
    existing = values.get("GROQ_API_KEY", "") or ""
    print("Groq mode sends your questions and recorded speech to Groq. It needs internet and your own API key; provider limits or charges may apply.")
    reuse = existing.startswith("gsk_") and input_fn("Use the Groq key already saved here? [Y/n]: ").strip().lower() != "n"
    key = existing if reuse else password_fn("Groq API key (hidden; Enter cancels): ").strip()
    if not key:
        print("Cancelled. Existing configuration is unchanged.")
        return False
    if not key.startswith("gsk_") or any(c.isspace() for c in key):
        raise RouterClientError("That does not look like a Groq key. Copy it from https://console.groq.com/keys and retry.")
    router_key = values.get("ROUTER_API_KEY") or ""
    if not router_key or router_key.startswith("replace_with_"):
        router_key = secrets.token_urlsafe(32)
    # Write atomically, with owner-only permissions on POSIX, without echoing keys.
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".env-setup-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(path.read_text(encoding="utf-8") if path.exists() else "")
        set_key(str(temporary), "GROQ_API_KEY", key)
        set_key(str(temporary), "ROUTER_API_KEY", router_key)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    write_settings({"provider": "router"})
    print(f"Groq mode selected. Credentials saved privately in {path}; they are not committed to Git.")
    print("The key format was checked; Groq authentication is checked when you use the service.")
    return True


def run_setup(*, input_fn=input, password_fn=getpass.getpass) -> int:
    print("\nHow would you like to run JARVIS?\n")
    print("  1. Locally with Ollama - no API key; checks RAM and downloads local models.")
    print("  2. Groq API - your own key; internet required; speech and chat use Groq.")
    print("  q. Cancel (keep current settings)")
    selection = input_fn("Choose 1 or 2: ").strip().lower()
    if selection == "q":
        return 0
    if selection not in {"1", "2"}:
        print("Choose 1 or 2. No settings changed.")
        return 1
    try:
        if selection == "1":
            install_requirements(BASE_DIR / "requirements-local.txt")
            from setup_local import run_setup as local_setup
            return local_setup(input_fn=input_fn)
        install_requirements(ROUTER_DIR / "requirements.txt")
        configure_cloud(input_fn=input_fn, password_fn=password_fn)
        return 0
    except (OSError, subprocess.SubprocessError, RouterClientError) as exc:
        print(f"Setup incomplete: {exc}")
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(run_setup())
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled.")
        raise SystemExit(1)

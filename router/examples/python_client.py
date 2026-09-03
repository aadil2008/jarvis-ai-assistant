from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from uuid import uuid4
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROUTER_URL = os.getenv("ROUTER_URL", "http://127.0.0.1:8000")


def _authorization_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    router_key = os.getenv("ROUTER_API_KEY")
    if router_key:
        headers["Authorization"] = f"Bearer {router_key}"
    return headers


def _read_response(request: Request) -> dict:
    try:
        with urlopen(request, timeout=90) as response:
            return json.load(response)
    except HTTPError as exc:
        error = json.loads(exc.read().decode("utf-8"))
        raise RuntimeError(error.get("message", "Router request failed")) from exc


def ask(message: str, agent: str = "jarvis", mode: str = "auto") -> dict:
    """Call the user's router. The Groq key always remains on the router server."""
    headers = _authorization_headers() | {"Content-Type": "application/json"}

    request = Request(
        f"{ROUTER_URL}/v1/chat",
        data=json.dumps({"message": message, "agent": agent, "mode": mode}).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    return _read_response(request)


def transcribe(audio_path: str | Path, language: str | None = None) -> dict:
    """Send an audio file to the router without exposing the Groq key."""
    path = Path(audio_path)
    boundary = f"JarvisBoundary{uuid4().hex}"
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    parts: list[bytes] = []

    if language:
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="language"\r\n\r\n',
                language.encode(),
                b"\r\n",
            ]
        )
    parts.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    headers = _authorization_headers() | {
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    }
    return _read_response(
        Request(
            f"{ROUTER_URL}/v1/transcribe",
            data=b"".join(parts),
            headers=headers,
            method="POST",
        )
    )


if __name__ == "__main__":
    result = ask("Explain how a binary search tree works.")
    print(result["answer"])
    print(f"Model: {result['model']} ({result['route']})")

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Callable


class RouterClientError(RuntimeError):
    """A safe, user-facing router failure."""


@dataclass(frozen=True)
class RouterReply:
    answer: str
    model: str
    route: str
    routing_reason: str


def _timeout_from_env() -> float:
    try:
        return max(1.0, float(os.getenv("JARVIS_ROUTER_TIMEOUT", "75")))
    except ValueError:
        return 75.0


class RouterClient:
    """Minimal client for the private multi-model router."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        opener: Callable | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("JARVIS_ROUTER_URL", "http://127.0.0.1:8000")
        ).rstrip("/")
        self.api_key = api_key or os.getenv("JARVIS_ROUTER_API_KEY") or os.getenv("ROUTER_API_KEY")
        self.timeout = timeout if timeout is not None else _timeout_from_env()
        self._opener = opener or urllib.request.urlopen

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @staticmethod
    def _decode_json(raw: bytes) -> dict:
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RouterClientError("The router returned an unreadable response.") from exc
        if not isinstance(value, dict):
            raise RouterClientError("The router returned an unexpected response.")
        return value

    def _request(self, request: urllib.request.Request) -> dict:
        response = None
        try:
            response = self._opener(request, timeout=self.timeout)
            return self._decode_json(response.read())
        except urllib.error.HTTPError as exc:
            try:
                payload = self._decode_json(exc.read())
                message = str(payload.get("message") or "").strip()
            except RouterClientError:
                message = ""
            if exc.code == 401:
                message = "The router key was rejected. Check JARVIS_ROUTER_API_KEY."
            elif not message:
                message = f"The router returned HTTP {exc.code}."
            raise RouterClientError(message) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RouterClientError(
                f"I could not reach the local router at {self.base_url}. Start it and try again."
            ) from exc
        finally:
            if response is not None:
                response.close()

    def health(self) -> bool:
        request = urllib.request.Request(
            f"{self.base_url}/health",
            headers=self._headers(),
            method="GET",
        )
        payload = self._request(request)
        return payload.get("status") == "ok"

    def chat(
        self,
        message: str,
        *,
        conversation: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 350,
    ) -> RouterReply:
        payload = {
            "message": message,
            "agent": "jarvis",
            "mode": "auto",
            "conversation": conversation or [],
            "max_tokens": max_tokens,
        }
        if system_prompt:
            payload["system_prompt"] = system_prompt
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers("application/json"),
            method="POST",
        )
        result = self._request(request)
        answer = str(result.get("answer") or "").strip()
        if not answer:
            raise RouterClientError("The router returned an empty answer.")
        return RouterReply(
            answer=answer,
            model=str(result.get("model") or "unknown"),
            route=str(result.get("route") or "unknown"),
            routing_reason=str(result.get("routing_reason") or ""),
        )

    def transcribe(self, wav_data: bytes, *, language: str = "en") -> str:
        if not wav_data:
            raise RouterClientError("No microphone audio was captured.")

        boundary = f"----JarvisBoundary{uuid.uuid4().hex}"
        chunks = [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="language"\r\n\r\n',
            language.encode("ascii"),
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="voice.wav"\r\n',
            b"Content-Type: audio/wav\r\n\r\n",
            wav_data,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        request = urllib.request.Request(
            f"{self.base_url}/v1/transcribe",
            data=b"".join(chunks),
            headers=self._headers(f"multipart/form-data; boundary={boundary}"),
            method="POST",
        )
        result = self._request(request)
        text = str(result.get("text") or "").strip()
        if not text:
            raise RouterClientError("Whisper could not detect any speech.")
        return text

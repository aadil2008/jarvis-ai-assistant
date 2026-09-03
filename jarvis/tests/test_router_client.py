from __future__ import annotations

import json
import sys
import unittest
import urllib.error
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from router_client import RouterClient, RouterClientError  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = json.dumps(payload).encode("utf-8")
        self.closed = False

    def read(self) -> bytes:
        return self.payload

    def close(self) -> None:
        self.closed = True


class RecordingOpener:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple] = []

    def __call__(self, request, *, timeout):
        self.calls.append((request, timeout))
        return FakeResponse(self.responses.pop(0))


class RouterClientTests(unittest.TestCase):
    def test_health_uses_local_endpoint(self) -> None:
        opener = RecordingOpener([{"status": "ok"}])
        client = RouterClient(base_url="http://127.0.0.1:9000/", opener=opener)

        self.assertTrue(client.health())
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:9000/health")
        self.assertEqual(request.method, "GET")
        self.assertEqual(timeout, 75.0)

    def test_chat_sends_auth_history_and_returns_route_metadata(self) -> None:
        opener = RecordingOpener(
            [
                {
                    "success": True,
                    "answer": "At your service.",
                    "model": "fast-model",
                    "route": "fast",
                    "routing_reason": "Simple request",
                }
            ]
        )
        client = RouterClient(base_url="http://router", api_key="private-router-key", opener=opener)
        reply = client.chat(
            "Hello",
            conversation=[{"role": "user", "content": "Earlier"}],
            system_prompt="Be concise.",
            max_tokens=120,
        )

        request, _ = opener.calls[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "http://router/v1/chat")
        self.assertEqual(request.get_header("Authorization"), "Bearer private-router-key")
        self.assertEqual(payload["agent"], "jarvis")
        self.assertEqual(payload["mode"], "auto")
        self.assertEqual(payload["conversation"][0]["content"], "Earlier")
        self.assertEqual(reply.answer, "At your service.")
        self.assertEqual(reply.model, "fast-model")
        self.assertEqual(reply.route, "fast")

    def test_transcription_sends_wav_to_whisper_endpoint(self) -> None:
        opener = RecordingOpener([{"success": True, "text": "open Safari", "model": "whisper"}])
        client = RouterClient(base_url="http://router", api_key="secret", opener=opener)

        text = client.transcribe(b"RIFF-audio-bytes")

        request, _ = opener.calls[0]
        self.assertEqual(text, "open Safari")
        self.assertEqual(request.full_url, "http://router/v1/transcribe")
        self.assertIn("multipart/form-data", request.get_header("Content-type"))
        self.assertIn(b'filename="voice.wav"', request.data)
        self.assertIn(b"RIFF-audio-bytes", request.data)

    def test_connection_error_does_not_expose_router_key(self) -> None:
        def fail(_request, *, timeout):
            raise urllib.error.URLError("offline")

        client = RouterClient(base_url="http://127.0.0.1:8000", api_key="do-not-leak", opener=fail)
        with self.assertRaises(RouterClientError) as context:
            client.health()
        self.assertNotIn("do-not-leak", str(context.exception))
        self.assertIn("Start it", str(context.exception))


if __name__ == "__main__":
    unittest.main()

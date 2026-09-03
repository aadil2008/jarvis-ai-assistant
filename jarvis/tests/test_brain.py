from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain import Brain, BrainConfig  # noqa: E402
from router_client import RouterClientError, RouterReply  # noqa: E402


class FakeRouterClient:
    def __init__(self) -> None:
        self.chat_calls: list[dict] = []
        self.transcription_calls: list[bytes] = []
        self.ready = True
        self.failure: RouterClientError | None = None

    def chat(self, message, **kwargs) -> RouterReply:
        self.chat_calls.append({"message": message, **kwargs})
        if self.failure:
            raise self.failure
        return RouterReply("Ready, sir.", "fast-model", "fast", "Simple request")

    def transcribe(self, wav_data, *, language) -> str:
        self.transcription_calls.append(wav_data)
        return "open Safari"

    def health(self) -> bool:
        if self.failure:
            raise self.failure
        return self.ready


class BrainTests(unittest.TestCase):
    def test_conversation_uses_router_and_preserves_history(self) -> None:
        client = FakeRouterClient()
        brain = Brain(client=client)

        first = brain.ask("Hello")
        second = brain.ask("What did I just say?")

        self.assertEqual(first, "Ready, sir.")
        self.assertEqual(second, "Ready, sir.")
        self.assertEqual(client.chat_calls[0]["conversation"], [])
        self.assertEqual(len(client.chat_calls[1]["conversation"]), 2)
        self.assertEqual(brain.last_model, "fast-model")
        self.assertEqual(brain.last_route, "fast")

    def test_failed_request_does_not_pollute_history(self) -> None:
        client = FakeRouterClient()
        client.failure = RouterClientError("Router unavailable.")
        brain = Brain(client=client)

        answer = brain.ask("Hello")

        self.assertIn("offline", answer)
        self.assertEqual(brain.history, [])

    def test_history_is_bounded(self) -> None:
        client = FakeRouterClient()
        brain = Brain(client=client, config=BrainConfig(max_history_messages=4))
        for number in range(4):
            brain.ask(f"Message {number}")
        self.assertEqual(len(brain.history), 4)
        self.assertEqual(brain.history[0]["content"], "Message 2")

    def test_transcription_uses_router(self) -> None:
        client = FakeRouterClient()
        brain = Brain(client=client)
        self.assertEqual(brain.transcribe(b"audio"), "open Safari")
        self.assertEqual(client.transcription_calls, [b"audio"])


if __name__ == "__main__":
    unittest.main()

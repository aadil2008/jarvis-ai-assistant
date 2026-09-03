from __future__ import annotations

import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient
from openai import RateLimitError

from app.config import Settings
from app.exceptions import UpstreamError
from app.groq_client import GroqClient, GroqResult, TranscriptionResult
from app.main import create_app
from app.models import UsageInfo


class FakeGroqClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.transcription_calls: list[dict] = []
        self.failures: dict[str, UpstreamError] = {}

    def chat(self, **kwargs) -> GroqResult:
        self.calls.append(kwargs)
        failure = self.failures.get(kwargs["model"])
        if failure:
            raise failure
        return GroqResult(
            answer="Mock answer",
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    def list_models(self) -> tuple[list[str], bool]:
        return ["coding-model", "fast-model", "smart-model", "speech-model", "web-model"], False

    def transcribe(self, **kwargs) -> TranscriptionResult:
        self.transcription_calls.append(kwargs)
        failure = self.failures.get(kwargs["model"])
        if failure:
            raise failure
        return TranscriptionResult(text="Hello from JARVIS")


class FakeOpenAIClient:
    def __init__(self, *, rate_limit_once: bool = False) -> None:
        self.completion_calls = 0
        self.transcription_calls = 0
        self.model_calls = 0
        self.transcription_calls = 0
        self.rate_limit_once = rate_limit_once
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create_completion))
        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=self.create_transcription))
        self.models = SimpleNamespace(list=self.list_models)

    def create_completion(self, **_kwargs):
        self.completion_calls += 1
        if self.rate_limit_once and self.completion_calls == 1:
            raise FakeRateLimitError()
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Recovered"))],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5),
        )

    def list_models(self):
        self.model_calls += 1
        return SimpleNamespace(data=[SimpleNamespace(id="model-b"), SimpleNamespace(id="model-a")])

    def create_transcription(self, **_kwargs):
        self.transcription_calls += 1
        return SimpleNamespace(text="Transcribed text")


class FakeRateLimitError(RateLimitError):
    """SDK-version-independent rate-limit error for retry tests."""

    def __init__(self) -> None:
        Exception.__init__(self, "rate limited")
        self.response = SimpleNamespace(headers={"retry-after": "0"})


class GroqClientTests(unittest.TestCase):
    def test_rate_limit_retries_only_once_and_respects_header(self) -> None:
        fake_openai = FakeOpenAIClient(rate_limit_once=True)
        delays: list[float] = []
        client = GroqClient(Settings(groq_api_key="fake"), client=fake_openai, sleep_fn=delays.append)
        result = client.chat(
            model="fast-model",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.3,
            max_tokens=20,
        )
        self.assertEqual(result.answer, "Recovered")
        self.assertEqual(result.attempts, 2)
        self.assertEqual(fake_openai.completion_calls, 2)
        self.assertEqual(delays, [0.0])

    def test_model_discovery_is_sorted_and_cached(self) -> None:
        fake_openai = FakeOpenAIClient()
        client = GroqClient(Settings(groq_api_key="fake"), client=fake_openai)
        first_models, first_cached = client.list_models()
        second_models, second_cached = client.list_models()
        self.assertEqual(first_models, ["model-a", "model-b"])
        self.assertFalse(first_cached)
        self.assertTrue(second_cached)
        self.assertEqual(second_models, first_models)
        self.assertEqual(fake_openai.model_calls, 1)

    def test_audio_transcription_uses_reusable_client(self) -> None:
        fake_openai = FakeOpenAIClient()
        client = GroqClient(Settings(groq_api_key="fake"), client=fake_openai)
        result = client.transcribe(
            model="speech-model",
            filename="sample.wav",
            content=b"RIFF",
            content_type="audio/wav",
            language="en",
            prompt=None,
            temperature=0.0,
        )
        self.assertEqual(result.text, "Transcribed text")
        self.assertEqual(fake_openai.transcription_calls, 1)


class APITests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            groq_api_key="fake-groq-key",
            router_api_key="router-secret",
            fast_model="fast-model",
            smart_model="smart-model",
            coding_model="coding-model",
            web_model="web-model",
            speech_model="speech-model",
            max_message_length=100,
            max_output_tokens_default=50,
            max_output_tokens_hard_limit=100,
            max_audio_file_size=16,
        )
        self.fake = FakeGroqClient()
        self.app = create_app(settings=self.settings, groq_client=self.fake)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.auth = {"Authorization": "Bearer router-secret"}

    def tearDown(self) -> None:
        self.client.close()

    def test_health_does_not_require_auth_or_groq(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(self.fake.transcription_calls, [])

    def test_protected_endpoint_rejects_missing_token(self) -> None:
        response = self.client.post("/v1/route", json={"message": "Hello"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "UNAUTHORIZED")

    def test_route_endpoint_does_not_call_groq(self) -> None:
        response = self.client.post(
            "/v1/route",
            headers=self.auth,
            json={"message": "Research today's AI news", "agent": "friday"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["route"], "web")
        self.assertEqual(self.fake.calls, [])

    def test_chat_returns_standard_response_and_message_order(self) -> None:
        response = self.client.post(
            "/v1/chat",
            headers=self.auth,
            json={
                "message": "Hello",
                "agent": "jarvis",
                "system_prompt": "Be concise.",
                "conversation": [
                    {"role": "user", "content": "Previous question"},
                    {"role": "assistant", "content": "Previous answer"},
                ],
            },
        )
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["success"])
        self.assertEqual(body["model"], "fast-model")
        self.assertEqual(body["usage"]["total_tokens"], 15)
        messages = self.fake.calls[0]["messages"]
        self.assertEqual([item["role"] for item in messages], ["system", "user", "assistant", "user"])
        self.assertIn("Be concise", messages[0]["content"])
        self.assertEqual(messages[-1]["content"], "Hello")

    def test_coding_request_uses_coding_model(self) -> None:
        response = self.client.post(
            "/v1/chat",
            headers=self.auth,
            json={"message": "Write a Python function to sort this list"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["route"], "coding")
        self.assertEqual(response.json()["model"], "coding-model")

    def test_smart_rate_limit_falls_back_to_fast(self) -> None:
        self.fake.failures["smart-model"] = UpstreamError(
            "RATE_LIMIT",
            "Model rate limit reached.",
            429,
            model="smart-model",
            retryable=True,
            attempts=2,
        )
        response = self.client.post(
            "/v1/chat",
            headers=self.auth,
            json={"message": "Analyze this complex architecture", "mode": "smart"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["route"], "fast")
        self.assertEqual([call["model"] for call in self.fake.calls], ["smart-model", "fast-model"])

    def test_web_failure_never_falls_back(self) -> None:
        self.fake.failures["web-model"] = UpstreamError(
            "RATE_LIMIT",
            "Model rate limit reached.",
            429,
            model="web-model",
            retryable=True,
            attempts=2,
        )
        response = self.client.post(
            "/v1/chat",
            headers=self.auth,
            json={"message": "Search today's latest news", "mode": "web"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "WEB_UNAVAILABLE")
        self.assertEqual([call["model"] for call in self.fake.calls], ["web-model"])

    def test_hard_token_limit_is_enforced_before_groq_call(self) -> None:
        response = self.client.post(
            "/v1/chat",
            headers=self.auth,
            json={"message": "Hello", "max_tokens": 101},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "MAX_TOKENS_EXCEEDED")
        self.assertEqual(self.fake.calls, [])

    def test_message_length_is_enforced(self) -> None:
        response = self.client.post(
            "/v1/chat",
            headers=self.auth,
            json={"message": "x" * 101},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "MESSAGE_TOO_LONG")

    def test_invalid_conversation_role_is_rejected(self) -> None:
        response = self.client.post(
            "/v1/chat",
            headers=self.auth,
            json={"message": "Hello", "conversation": [{"role": "system", "content": "bad"}]},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "INVALID_REQUEST")

    def test_models_endpoint(self) -> None:
        response = self.client.get("/v1/models")
        self.assertEqual(response.status_code, 200)
        self.assertIn("coding-model", response.json()["models"])
        self.assertIn("speech-model", response.json()["models"])

    def test_transcription_is_authenticated_and_uses_speech_model(self) -> None:
        unauthorized = self.client.post(
            "/v1/transcribe",
            files={"file": ("sample.wav", b"RIFF", "audio/wav")},
        )
        self.assertEqual(unauthorized.status_code, 401)

        response = self.client.post(
            "/v1/transcribe",
            headers=self.auth,
            files={"file": ("sample.wav", b"RIFF", "audio/wav")},
            data={"language": "en"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "Hello from JARVIS")
        self.assertEqual(response.json()["model"], "speech-model")
        self.assertEqual(self.fake.transcription_calls[0]["language"], "en")

    def test_transcription_rejects_unsupported_or_large_audio(self) -> None:
        unsupported = self.client.post(
            "/v1/transcribe",
            headers=self.auth,
            files={"file": ("sample.txt", b"audio", "text/plain")},
        )
        self.assertEqual(unsupported.status_code, 400)
        self.assertEqual(unsupported.json()["error"], "UNSUPPORTED_AUDIO_FORMAT")

        too_large = self.client.post(
            "/v1/transcribe",
            headers=self.auth,
            files={"file": ("sample.wav", b"x" * 17, "audio/wav")},
        )
        self.assertEqual(too_large.status_code, 400)
        self.assertEqual(too_large.json()["error"], "AUDIO_FILE_TOO_LARGE")

    def test_stats_are_protected_and_include_usage(self) -> None:
        self.client.post("/v1/chat", headers=self.auth, json={"message": "Hello"})
        response = self.client.get("/v1/stats", headers=self.auth)
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["total_requests"], 1)
        self.assertEqual(body["models"]["fast-model"]["tokens"], 15)

    def test_unknown_endpoint_returns_standard_error(self) -> None:
        response = self.client.get("/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()

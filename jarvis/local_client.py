"""Local-only inference. No router calls or implicit speech-model downloads."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from local_settings import MODEL_DIR, load_settings, local_model
from router_client import RouterClientError, RouterReply

OLLAMA_URL = "http://127.0.0.1:11434"


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_opener():
    # Ignore HTTP_PROXY; even a configured proxy must not receive local prompts.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects()).open


class LocalClient:
    def __init__(self, settings=None, opener=None, transcriber_factory=None, model_dir: Path = MODEL_DIR):
        settings = load_settings() if settings is None else settings
        self.model = local_model(settings)
        self.whisper_name = settings.get("whisper_model", "tiny.en")
        if self.whisper_name not in {"tiny.en", "base.en"}:
            raise RouterClientError("Unsupported speech model. Re-run local setup.")
        self.whisper_path = model_dir / f"whisper-{self.whisper_name}"
        self._opener = opener or local_opener()
        self._transcriber_factory = transcriber_factory
        self._transcriber = None

    def _request(self, endpoint, payload=None, timeout=120):
        request = urllib.request.Request(
            OLLAMA_URL + endpoint,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self._opener(request, timeout=timeout) as response:
                result = json.loads(response.read().decode())
            if not isinstance(result, dict) or result.get("error"):
                raise ValueError("invalid response")
            return result
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                message = f"Ollama model missing. Run local setup or ollama pull {self.model}."
            else:
                message = "Ollama could not complete the request. Check its version and free RAM, then try a smaller model."
            raise RouterClientError(message) from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise RouterClientError("Local Ollama is unavailable or timed out. Open Ollama (or run ollama serve), then try again. No cloud fallback was used.") from exc
        except (ValueError, UnicodeError) as exc:
            raise RouterClientError("Ollama returned an unreadable response. Update Ollama and try again.") from exc

    def health(self) -> bool:
        data = self._request("/api/tags", timeout=5)
        installed = {m.get("name") for m in data.get("models", []) if isinstance(m, dict)}
        if self.model not in installed:
            raise RouterClientError(f"Download {self.model} with Setup_Jarvis first.")
        return True

    def voice_ready(self) -> bool:
        return all((self.whisper_path / name).is_file() for name in ("model.bin", "config.json", "tokenizer.json"))

    def chat(self, message, *, conversation=None, system_prompt=None, max_tokens=350):
        if len(message) > 2000:
            raise RouterClientError("Please shorten this question to 2,000 characters for the local voice model.")
        history, remaining = [], 2000
        for item in reversed((conversation or [])[-6:]):
            text = item.get("content", "")
            if len(text) > remaining:
                break
            history.insert(0, {"role": item["role"], "content": text})
            remaining -= len(text)
        prompt = (system_prompt or "You are JARVIS.") + " You are running locally without web research. Do not claim to know live facts."
        result = self._request("/api/chat", {
            "model": self.model,
            "messages": [{"role": "system", "content": prompt}] + history + [{"role": "user", "content": message}],
            "stream": False, "think": False, "keep_alive": "2m",
            "options": {"num_ctx": 2048, "num_predict": min(max_tokens, 350), "temperature": 0.3},
        })
        reply = result.get("message")
        answer = reply.get("content", "") if isinstance(reply, dict) else ""
        if not isinstance(answer, str) or not answer.strip() or result.get("done") is not True:
            raise RouterClientError("Ollama did not return a complete answer. Try a shorter question or a smaller model.")
        return RouterReply(answer.strip(), self.model, "local", "On-device Ollama; no cloud fallback")

    def transcribe(self, wav_data: bytes, *, language="en") -> str:
        if not wav_data:
            raise RouterClientError("No microphone audio was captured.")
        if not self.voice_ready():
            raise RouterClientError("Offline speech model is missing. Re-run Setup_Jarvis with internet access once.")
        try:
            if self._transcriber is None:
                if self._transcriber_factory is None:
                    from faster_whisper import WhisperModel
                    self._transcriber_factory = WhisperModel
                self._transcriber = self._transcriber_factory(
                    str(self.whisper_path), device="cpu", compute_type="int8",
                    cpu_threads=max(1, min(4, os.cpu_count() or 1)), local_files_only=True,
                )
            segments, _ = self._transcriber.transcribe(io.BytesIO(wav_data), language=language, beam_size=1)
            text = " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as exc:
            raise RouterClientError("Offline speech recognition failed. Check the microphone recording and re-run setup if model files are damaged.") from exc
        if not text:
            raise RouterClientError("No speech was detected.")
        return text

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


SYSTEM_PROMPT = (
    "You are JARVIS, a calm, capable, and precise personal desktop assistant. "
    "Respond naturally and directly, with subtle wit when appropriate. Default to one "
    "to four concise sentences. Do not add tutorials, exercises, code, long lists, or "
    "unrequested advice. Never use emojis unless the user asks for them. Never claim "
    "that you opened, changed, found, or controlled something on the computer unless "
    "the local program has confirmed that action. If a requested ability is unavailable, "
    "say so honestly and briefly. The local program can open applications, open websites, "
    "search the web, find files, read today's Apple Calendar events with permission, take "
    "screenshots, report the time and date, and control volume. If a computer request was "
    "not understood, suggest one clear command using those abilities instead of claiming "
    "that JARVIS cannot interact with apps or the web."
)


@dataclass
class BrainConfig:
    model: str = os.getenv("JARVIS_MODEL", "gpt-4o-mini")
    max_output_tokens: int = 350
    base_url: str | None = os.getenv("JARVIS_BASE_URL")


class Brain:
    def __init__(
        self,
        api_key: str | None = None,
        api_key_path: Path | None = None,
        config: BrainConfig | None = None,
    ) -> None:
        self.active = False
        self.client = None
        self.last_error = ""
        self.config = config or BrainConfig()
        self.provider = "OpenAI"
        self.history: list[dict[str, str]] = []

        key = api_key or self._load_api_key(api_key_path)
        if not key:
            self.last_error = "No API key was found."
            return

        if OpenAI is None:
            self.last_error = "The OpenAI package is not installed."
            return

        if key.startswith("gsk_"):
            self.provider = "Groq"
            if not self.config.base_url:
                self.config.base_url = "https://api.groq.com/openai/v1"
            if not os.getenv("JARVIS_MODEL"):
                self.config.model = "openai/gpt-oss-20b"

        try:
            client_options: dict[str, str] = {"api_key": key}
            if self.config.base_url:
                client_options["base_url"] = self.config.base_url
            self.client = OpenAI(**client_options)
            self.active = True
        except Exception as exc:
            self.last_error = f"Could not initialize the AI client: {exc}"

    @staticmethod
    def _load_api_key(api_key_path: Path | None) -> str | None:
        env_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        if env_key:
            return env_key.strip()

        path = api_key_path or Path(__file__).resolve().parent / "api_key.txt"
        try:
            value = path.read_text(encoding="utf-8-sig").strip()
            return value or None
        except (OSError, UnicodeError):
            return None

    def _trim_history(self, max_messages: int = 16) -> None:
        self.history = self.history[-max_messages:]

    def ask(self, query: str, context: str | None = None) -> str:
        if not self.active or self.client is None:
            reason = self.last_error or "The AI service is unavailable."
            return f"My AI brain is offline. {reason} Local commands still work."

        cleaned_query = query.strip()
        if not cleaned_query:
            return "What would you like help with?"

        content = cleaned_query
        if context:
            content = f"Current student context:\n{context}\n\nRequest:\n{cleaned_query}"

        self.history.append({"role": "user", "content": content})
        self._trim_history()

        try:
            # The Responses API is the current OpenAI interface for text generation.
            if hasattr(self.client, "responses"):
                request = {
                    "model": self.config.model,
                    "instructions": SYSTEM_PROMPT,
                    "input": self.history,
                    "max_output_tokens": self.config.max_output_tokens,
                }
                if self.provider == "OpenAI":
                    request["store"] = False
                response = self.client.responses.create(
                    **request,
                )
                reply = (response.output_text or "").strip()
            else:
                # Compatibility path for an older installed OpenAI package.
                messages = [{"role": "system", "content": SYSTEM_PROMPT}, *self.history]
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    max_tokens=self.config.max_output_tokens,
                )
                reply = (response.choices[0].message.content or "").strip()

            if not reply:
                reply = "I could not generate a response. Please try rephrasing the question."
            self.history.append({"role": "assistant", "content": reply})
            self._trim_history()
            return reply
        except Exception as exc:
            return f"The AI request failed: {exc}"

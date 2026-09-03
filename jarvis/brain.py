from __future__ import annotations

from dataclasses import dataclass

from router_client import RouterClient, RouterClientError


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


@dataclass(frozen=True)
class BrainConfig:
    max_output_tokens: int = 350
    max_history_messages: int = 16


class Brain:
    """Conversation state backed by the private multi-model router."""

    def __init__(
        self,
        client: RouterClient | None = None,
        config: BrainConfig | None = None,
    ) -> None:
        self.client = client or RouterClient()
        self.config = config or BrainConfig()
        self.provider = "multi-model router"
        self.history: list[dict[str, str]] = []
        self.last_error = ""
        self.last_model = ""
        self.last_route = ""

    def _trim_history(self) -> None:
        self.history = self.history[-self.config.max_history_messages :]

    def ask(self, query: str, context: str | None = None) -> str:
        cleaned_query = query.strip()
        if not cleaned_query:
            return "What would you like help with?"

        content = cleaned_query
        if context:
            content = f"Current student context:\n{context}\n\nRequest:\n{cleaned_query}"

        try:
            response = self.client.chat(
                content,
                conversation=[dict(message) for message in self.history],
                system_prompt=SYSTEM_PROMPT,
                max_tokens=self.config.max_output_tokens,
            )
        except RouterClientError as exc:
            self.last_error = str(exc)
            return f"My AI brain is offline. {exc} Local commands still work."

        self.last_error = ""
        self.last_model = response.model
        self.last_route = response.route
        self.history.extend(
            [
                {"role": "user", "content": content},
                {"role": "assistant", "content": response.answer},
            ]
        )
        self._trim_history()
        return response.answer

    def transcribe(self, wav_data: bytes) -> str:
        return self.client.transcribe(wav_data, language="en")

    def router_is_ready(self) -> bool:
        try:
            ready = self.client.health()
        except RouterClientError as exc:
            self.last_error = str(exc)
            return False
        self.last_error = "" if ready else "The router health check did not pass."
        return ready

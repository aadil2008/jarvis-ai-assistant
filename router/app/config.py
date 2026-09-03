from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


@dataclass(frozen=True)
class Settings:
    groq_api_key: str | None = None
    router_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    fast_model: str = "openai/gpt-oss-20b"
    smart_model: str = "openai/gpt-oss-120b"
    coding_model: str = "qwen/qwen3.8-27b"
    web_model: str = "groq/compound"
    speech_model: str = "whisper-large-v3-turbo"
    max_output_tokens_default: int = 1500
    max_output_tokens_hard_limit: int = 4000
    max_message_length: int = 20_000
    max_conversation_messages: int = 50
    max_conversation_length: int = 60_000
    max_audio_file_size: int = 25 * 1024 * 1024
    model_cache_ttl_seconds: int = 300
    groq_timeout_seconds: float = 60.0
    retry_after_max_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.max_output_tokens_default < 1:
            raise ValueError("MAX_OUTPUT_TOKENS_DEFAULT must be positive")
        if self.max_output_tokens_hard_limit < self.max_output_tokens_default:
            raise ValueError(
                "MAX_OUTPUT_TOKENS_HARD_LIMIT must be greater than or equal to "
                "MAX_OUTPUT_TOKENS_DEFAULT"
            )
        if self.max_message_length < 1:
            raise ValueError("MAX_MESSAGE_LENGTH must be positive")
        if self.max_conversation_messages < 0 or self.max_conversation_length < 0:
            raise ValueError("Conversation limits cannot be negative")
        if self.max_audio_file_size < 1:
            raise ValueError("MAX_AUDIO_FILE_SIZE must be positive")
        if self.model_cache_ttl_seconds < 0:
            raise ValueError("MODEL_CACHE_TTL_SECONDS cannot be negative")
        if self.groq_timeout_seconds <= 0 or self.retry_after_max_seconds < 0:
            raise ValueError("Timeout values are invalid")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            router_api_key=os.getenv("ROUTER_API_KEY") or None,
            groq_base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            fast_model=os.getenv("FAST_MODEL", "openai/gpt-oss-20b"),
            smart_model=os.getenv("SMART_MODEL", "openai/gpt-oss-120b"),
            coding_model=os.getenv("CODING_MODEL", "qwen/qwen3.8-27b"),
            web_model=os.getenv("WEB_MODEL", "groq/compound"),
            speech_model=os.getenv("SPEECH_MODEL", "whisper-large-v3-turbo"),
            max_output_tokens_default=_env_int("MAX_OUTPUT_TOKENS_DEFAULT", 1500),
            max_output_tokens_hard_limit=_env_int("MAX_OUTPUT_TOKENS_HARD_LIMIT", 4000),
            max_message_length=_env_int("MAX_MESSAGE_LENGTH", 20_000),
            max_conversation_messages=_env_int("MAX_CONVERSATION_MESSAGES", 50),
            max_conversation_length=_env_int("MAX_CONVERSATION_LENGTH", 60_000),
            max_audio_file_size=_env_int("MAX_AUDIO_FILE_SIZE", 25 * 1024 * 1024),
            model_cache_ttl_seconds=_env_int("MODEL_CACHE_TTL_SECONDS", 300),
            groq_timeout_seconds=_env_float("GROQ_TIMEOUT_SECONDS", 60.0),
            retry_after_max_seconds=_env_float("RETRY_AFTER_MAX_SECONDS", 5.0),
        )

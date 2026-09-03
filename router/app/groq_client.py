from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import Lock
from typing import Callable

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from app.config import Settings
from app.exceptions import RouterError, UpstreamError
from app.models import UsageInfo


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroqResult:
    answer: str
    usage: UsageInfo
    attempts: int = 1


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    attempts: int = 1


class GroqClient:
    """One reusable OpenAI-compatible client configured for Groq."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: OpenAI | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self._sleep = sleep_fn
        self._models_lock = Lock()
        self._model_cache: list[str] | None = None
        self._model_cache_expires_at = 0.0

        if client is not None:
            self._client = client
        elif settings.groq_api_key:
            self._client = OpenAI(
                api_key=settings.groq_api_key,
                base_url=settings.groq_base_url,
                timeout=settings.groq_timeout_seconds,
                max_retries=0,
            )
        else:
            self._client = None

    def _require_client(self) -> OpenAI:
        if self._client is None:
            raise RouterError(
                "SERVICE_UNAVAILABLE",
                "GROQ_API_KEY is not configured on the router server.",
                503,
            )
        return self._client

    def _retry_delay(self, exc: RateLimitError) -> float:
        header = None
        response = getattr(exc, "response", None)
        if response is not None:
            header = response.headers.get("retry-after")
        if not header:
            return min(1.0, self.settings.retry_after_max_seconds)
        try:
            delay = float(header)
        except ValueError:
            try:
                target = parsedate_to_datetime(header)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                delay = max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                delay = 1.0
        return min(max(0.0, delay), self.settings.retry_after_max_seconds)

    @staticmethod
    def _usage_from(response: object) -> UsageInfo:
        usage = getattr(response, "usage", None)
        if usage is None:
            return UsageInfo()
        return UsageInfo(
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )

    @staticmethod
    def _upstream_error(exc: Exception, model: str, attempts: int) -> UpstreamError:
        if isinstance(exc, RateLimitError):
            return UpstreamError(
                "RATE_LIMIT",
                "Model rate limit reached.",
                429,
                model=model,
                retryable=True,
                attempts=attempts,
            )
        if isinstance(exc, AuthenticationError):
            return UpstreamError(
                "UPSTREAM_AUTHENTICATION_FAILED",
                "Groq rejected the server API key.",
                503,
                model=model,
                retryable=False,
                attempts=attempts,
            )
        if isinstance(exc, PermissionDeniedError):
            return UpstreamError(
                "UPSTREAM_PERMISSION_DENIED",
                "Groq denied access to the selected model.",
                403,
                model=model,
                retryable=False,
                attempts=attempts,
            )
        if isinstance(exc, NotFoundError):
            return UpstreamError(
                "MODEL_NOT_FOUND",
                "The configured Groq model was not found.",
                404,
                model=model,
                retryable=False,
                attempts=attempts,
            )
        if isinstance(exc, BadRequestError):
            return UpstreamError(
                "UPSTREAM_BAD_REQUEST",
                "Groq rejected the model request.",
                400,
                model=model,
                retryable=False,
                attempts=attempts,
            )
        if isinstance(exc, APIConnectionError):
            return UpstreamError(
                "UPSTREAM_UNAVAILABLE",
                "Could not connect to Groq.",
                503,
                model=model,
                retryable=True,
                attempts=attempts,
            )
        if isinstance(exc, APIStatusError):
            status = int(getattr(exc, "status_code", 500) or 500)
            retryable = status >= 500
            return UpstreamError(
                "UPSTREAM_UNAVAILABLE" if retryable else "UPSTREAM_ERROR",
                "Groq is temporarily unavailable." if retryable else "Groq rejected the request.",
                503 if retryable else status,
                model=model,
                retryable=retryable,
                attempts=attempts,
            )
        return UpstreamError(
            "INTERNAL_ERROR",
            "Unexpected model client failure.",
            500,
            model=model,
            retryable=False,
            attempts=attempts,
        )

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> GroqResult:
        client = self._require_client()
        attempts = 0

        while attempts < 2:
            attempts += 1
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                answer = (response.choices[0].message.content or "").strip()
                if not answer:
                    raise UpstreamError(
                        "EMPTY_RESPONSE",
                        "The selected model returned an empty response.",
                        503,
                        model=model,
                        retryable=True,
                        attempts=attempts,
                    )
                return GroqResult(answer=answer, usage=self._usage_from(response), attempts=attempts)
            except RateLimitError as exc:
                if attempts == 1:
                    delay = self._retry_delay(exc)
                    logger.warning("Groq rate limit; retrying once after %.2f seconds", delay)
                    self._sleep(delay)
                    continue
                raise self._upstream_error(exc, model, attempts) from exc
            except UpstreamError:
                raise
            except Exception as exc:
                raise self._upstream_error(exc, model, attempts) from exc

        raise UpstreamError(
            "UPSTREAM_UNAVAILABLE",
            "Groq is temporarily unavailable.",
            503,
            model=model,
            retryable=True,
            attempts=attempts,
        )

    def list_models(self) -> tuple[list[str], bool]:
        now = time.monotonic()
        with self._models_lock:
            if self._model_cache is not None and now < self._model_cache_expires_at:
                return list(self._model_cache), True

        client = self._require_client()
        try:
            response = client.models.list()
            models = sorted({item.id for item in response.data})
        except Exception as exc:
            raise self._upstream_error(exc, "model-discovery", 1) from exc

        with self._models_lock:
            self._model_cache = models
            self._model_cache_expires_at = now + self.settings.model_cache_ttl_seconds
        return list(models), False

    def transcribe(
        self,
        *,
        model: str,
        filename: str,
        content: bytes,
        content_type: str,
        language: str | None,
        prompt: str | None,
        temperature: float,
    ) -> TranscriptionResult:
        client = self._require_client()
        attempts = 0
        request: dict[str, object] = {
            "model": model,
            "file": (filename, content, content_type),
            "response_format": "json",
            "temperature": temperature,
        }
        if language:
            request["language"] = language
        if prompt:
            request["prompt"] = prompt

        while attempts < 2:
            attempts += 1
            try:
                response = client.audio.transcriptions.create(**request)
                return TranscriptionResult(text=str(getattr(response, "text", "")), attempts=attempts)
            except RateLimitError as exc:
                if attempts == 1:
                    delay = self._retry_delay(exc)
                    logger.warning("Groq speech rate limit; retrying once after %.2f seconds", delay)
                    self._sleep(delay)
                    continue
                raise self._upstream_error(exc, model, attempts) from exc
            except Exception as exc:
                raise self._upstream_error(exc, model, attempts) from exc

        raise UpstreamError(
            "UPSTREAM_UNAVAILABLE",
            "Groq speech recognition is temporarily unavailable.",
            503,
            model=model,
            retryable=True,
            attempts=attempts,
        )

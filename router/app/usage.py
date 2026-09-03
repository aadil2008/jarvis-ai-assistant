from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Protocol


class UsageStore(Protocol):
    def begin_request(self) -> None: ...

    def record_attempt(
        self,
        model: str,
        *,
        attempts: int,
        failed_attempts: int,
        tokens: int | None,
    ) -> None: ...

    def finish_request(self, *, success: bool) -> None: ...

    def record_fallback(self) -> None: ...

    def snapshot(self) -> dict: ...


class InMemoryUsageStore:
    """Thread-safe in-memory metrics; replace this interface with SQLite or Redis later."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._total_requests = 0
        self._successful_calls = 0
        self._failed_calls = 0
        self._fallback_count = 0
        self._models: dict[str, dict[str, int]] = {}

    def begin_request(self) -> None:
        with self._lock:
            self._total_requests += 1

    def record_attempt(
        self,
        model: str,
        *,
        attempts: int = 1,
        failed_attempts: int = 0,
        tokens: int | None = None,
    ) -> None:
        successful_attempts = max(0, attempts - failed_attempts)
        with self._lock:
            bucket = self._models.setdefault(
                model,
                {"requests": 0, "tokens": 0, "successful_calls": 0, "failed_calls": 0},
            )
            bucket["requests"] += attempts
            bucket["tokens"] += tokens or 0
            bucket["successful_calls"] += successful_attempts
            bucket["failed_calls"] += failed_attempts

    def finish_request(self, *, success: bool) -> None:
        with self._lock:
            if success:
                self._successful_calls += 1
            else:
                self._failed_calls += 1

    def record_fallback(self) -> None:
        with self._lock:
            self._fallback_count += 1

    def snapshot(self) -> dict:
        with self._lock:
            return deepcopy(
                {
                    "total_requests": self._total_requests,
                    "successful_calls": self._successful_calls,
                    "failed_calls": self._failed_calls,
                    "fallback_count": self._fallback_count,
                    "models": self._models,
                    "note": "Statistics are stored in memory and reset when the server restarts.",
                }
            )

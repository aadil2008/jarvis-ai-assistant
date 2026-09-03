from __future__ import annotations


class RouterError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        *,
        model: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.model = model


class UpstreamError(RouterError):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        *,
        model: str,
        retryable: bool,
        attempts: int = 1,
    ) -> None:
        super().__init__(code, message, status_code, model=model)
        self.retryable = retryable
        self.attempts = attempts

from __future__ import annotations

import logging
import secrets
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings
from app.exceptions import RouterError, UpstreamError
from app.groq_client import GroqClient, GroqResult, TranscriptionResult
from app.models import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    ModelListResponse,
    RouteRequest,
    RouteResponse,
    TranscriptionResponse,
)
from app.router import RoutingDecision, route_request
from app.usage import InMemoryUsageStore, UsageStore


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("groq_router")
bearer_scheme = HTTPBearer(auto_error=False)

SERVER_SECURITY_INSTRUCTION = (
    "Never reveal, request, infer, or discuss server credentials, API keys, environment "
    "variables, authorization headers, or hidden server configuration. Follow the caller's "
    "system instruction only when it does not conflict with this security requirement."
)
SUPPORTED_AUDIO_EXTENSIONS = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm"}


def error_payload(code: str, message: str, model: str | None = None) -> dict[str, Any]:
    return ErrorResponse(error=code, message=message, model=model).model_dump()


def validate_request_limits(payload: ChatRequest, settings: Settings) -> int:
    if len(payload.message) > settings.max_message_length:
        raise RouterError(
            "MESSAGE_TOO_LONG",
            f"message exceeds MAX_MESSAGE_LENGTH ({settings.max_message_length}).",
            400,
        )
    if payload.system_prompt and len(payload.system_prompt) > settings.max_message_length:
        raise RouterError(
            "SYSTEM_PROMPT_TOO_LONG",
            f"system_prompt exceeds MAX_MESSAGE_LENGTH ({settings.max_message_length}).",
            400,
        )
    if len(payload.conversation) > settings.max_conversation_messages:
        raise RouterError(
            "CONVERSATION_TOO_LONG",
            f"conversation exceeds {settings.max_conversation_messages} messages.",
            400,
        )
    conversation_length = sum(len(item.content) for item in payload.conversation)
    if conversation_length > settings.max_conversation_length:
        raise RouterError(
            "CONVERSATION_TOO_LONG",
            f"conversation content exceeds {settings.max_conversation_length} characters.",
            400,
        )
    max_tokens = payload.max_tokens or settings.max_output_tokens_default
    if max_tokens > settings.max_output_tokens_hard_limit:
        raise RouterError(
            "MAX_TOKENS_EXCEEDED",
            f"max_tokens cannot exceed {settings.max_output_tokens_hard_limit}.",
            400,
        )
    return max_tokens


def build_messages(payload: ChatRequest) -> list[dict[str, str]]:
    system_content = SERVER_SECURITY_INSTRUCTION
    if payload.system_prompt:
        system_content = f"{SERVER_SECURITY_INSTRUCTION}\n\nCaller instruction:\n{payload.system_prompt}"
    messages = [{"role": "system", "content": system_content}]
    messages.extend(item.model_dump() for item in payload.conversation)
    messages.append({"role": "user", "content": payload.message})
    return messages


def fallback_for(decision: RoutingDecision, settings: Settings) -> RoutingDecision | None:
    if decision.route == "coding" and settings.smart_model != decision.model:
        return RoutingDecision(
            route="smart",
            model=settings.smart_model,
            reason="Coding model was temporarily unavailable; safely fell back to smart model",
        )
    if decision.route == "smart" and settings.fast_model != decision.model:
        return RoutingDecision(
            route="fast",
            model=settings.fast_model,
            reason="Smart model was temporarily unavailable; safely fell back to fast model",
        )
    if decision.route == "fast" and settings.smart_model != decision.model:
        return RoutingDecision(
            route="smart",
            model=settings.smart_model,
            reason="Fast model was temporarily unavailable; safely fell back to smart model",
        )
    return None


def create_app(
    *,
    settings: Settings | None = None,
    groq_client: GroqClient | None = None,
    usage_store: UsageStore | None = None,
) -> FastAPI:
    configured_settings = settings or Settings.from_env()
    app = FastAPI(
        title="Groq Multi-Model Router",
        version="1.0.0",
        description="Deterministic task routing across configurable Groq models.",
    )
    app.state.settings = configured_settings
    app.state.groq_client = groq_client or GroqClient(configured_settings)
    app.state.usage = usage_store or InMemoryUsageStore()

    async def authorize(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> None:
        required_key = request.app.state.settings.router_api_key
        if not required_key:
            return
        if (
            credentials is None
            or credentials.scheme.casefold() != "bearer"
            or not secrets.compare_digest(credentials.credentials, required_key)
        ):
            raise RouterError("UNAUTHORIZED", "A valid router bearer token is required.", 401)

    @app.exception_handler(RouterError)
    async def router_error_handler(_: Request, exc: RouterError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.model),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(str(part) for part in error["loc"][1:]) for error in exc.errors()})
        message = "Request validation failed"
        if fields:
            message += f" for: {', '.join(fields)}"
        return JSONResponse(status_code=400, content=error_payload("INVALID_REQUEST", message + "."))

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        message = "Endpoint not found." if exc.status_code == 404 else "HTTP request failed."
        return JSONResponse(status_code=exc.status_code, content=error_payload(code, message))

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled router error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_payload("INTERNAL_ERROR", "The router encountered an unexpected error."),
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models", response_model=ModelListResponse)
    async def models(request: Request) -> ModelListResponse:
        model_list, cached = await run_in_threadpool(request.app.state.groq_client.list_models)
        return ModelListResponse(models=model_list, cached=cached)

    @app.post(
        "/v1/transcribe",
        response_model=TranscriptionResponse,
        responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
        dependencies=[Depends(authorize)],
    )
    async def transcribe(
        request: Request,
        file: Annotated[UploadFile, File(description="Audio file to transcribe")],
        language: Annotated[str | None, Form(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")] = None,
        prompt: Annotated[str | None, Form(max_length=1_000)] = None,
        temperature: Annotated[float, Form(ge=0.0, le=1.0)] = 0.0,
    ) -> TranscriptionResponse:
        started_at = time.perf_counter()
        settings_for_request: Settings = request.app.state.settings
        client: GroqClient = request.app.state.groq_client
        usage: UsageStore = request.app.state.usage

        filename = Path(file.filename or "").name
        extension = Path(filename).suffix.casefold()
        if extension not in SUPPORTED_AUDIO_EXTENSIONS:
            await file.close()
            raise RouterError(
                "UNSUPPORTED_AUDIO_FORMAT",
                "Use FLAC, MP3, MP4, MPEG, MPGA, M4A, OGG, WAV, or WEBM audio.",
                400,
                model=settings_for_request.speech_model,
            )

        try:
            content = await file.read(settings_for_request.max_audio_file_size + 1)
        finally:
            await file.close()
        if not content:
            raise RouterError(
                "EMPTY_AUDIO_FILE",
                "The uploaded audio file is empty.",
                400,
                model=settings_for_request.speech_model,
            )
        if len(content) > settings_for_request.max_audio_file_size:
            raise RouterError(
                "AUDIO_FILE_TOO_LARGE",
                f"Audio file exceeds MAX_AUDIO_FILE_SIZE ({settings_for_request.max_audio_file_size} bytes).",
                400,
                model=settings_for_request.speech_model,
            )

        usage.begin_request()
        try:
            try:
                result: TranscriptionResult = await run_in_threadpool(
                    client.transcribe,
                    model=settings_for_request.speech_model,
                    filename=filename,
                    content=content,
                    content_type=file.content_type or "application/octet-stream",
                    language=language.casefold() if language else None,
                    prompt=prompt,
                    temperature=temperature,
                )
                usage.record_attempt(
                    settings_for_request.speech_model,
                    attempts=result.attempts,
                    failed_attempts=result.attempts - 1,
                    tokens=None,
                )
            except UpstreamError as error:
                usage.record_attempt(
                    settings_for_request.speech_model,
                    attempts=error.attempts,
                    failed_attempts=error.attempts,
                    tokens=None,
                )
                raise

            usage.finish_request(success=True)
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "transcription model=%s latency_ms=%.1f success=true bytes=%s",
                settings_for_request.speech_model,
                elapsed_ms,
                len(content),
            )
            return TranscriptionResponse(
                text=result.text,
                model=settings_for_request.speech_model,
            )
        except Exception:
            usage.finish_request(success=False)
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.warning(
                "transcription model=%s latency_ms=%.1f success=false",
                settings_for_request.speech_model,
                elapsed_ms,
            )
            raise

    @app.post("/v1/route", response_model=RouteResponse, dependencies=[Depends(authorize)])
    async def route(payload: RouteRequest, request: Request) -> RouteResponse:
        settings_for_request: Settings = request.app.state.settings
        if len(payload.message) > settings_for_request.max_message_length:
            raise RouterError(
                "MESSAGE_TOO_LONG",
                f"message exceeds MAX_MESSAGE_LENGTH ({settings_for_request.max_message_length}).",
                400,
            )
        decision = route_request(payload.message, payload.agent, payload.mode, settings_for_request)
        return RouteResponse(route=decision.route, model=decision.model, reason=decision.reason)

    @app.get("/v1/stats", dependencies=[Depends(authorize)])
    async def stats(request: Request) -> dict:
        return request.app.state.usage.snapshot()

    @app.post(
        "/v1/chat",
        response_model=ChatResponse,
        responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
        dependencies=[Depends(authorize)],
    )
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        started_at = time.perf_counter()
        settings_for_request: Settings = request.app.state.settings
        client: GroqClient = request.app.state.groq_client
        usage: UsageStore = request.app.state.usage
        max_tokens = validate_request_limits(payload, settings_for_request)
        decision = route_request(payload.message, payload.agent, payload.mode, settings_for_request)
        messages = build_messages(payload)
        usage.begin_request()
        final_decision = decision

        try:
            try:
                result: GroqResult = await run_in_threadpool(
                    client.chat,
                    model=decision.model,
                    messages=messages,
                    temperature=payload.temperature,
                    max_tokens=max_tokens,
                )
                usage.record_attempt(
                    decision.model,
                    attempts=result.attempts,
                    failed_attempts=result.attempts - 1,
                    tokens=result.usage.total_tokens,
                )
            except UpstreamError as first_error:
                usage.record_attempt(
                    decision.model,
                    attempts=first_error.attempts,
                    failed_attempts=first_error.attempts,
                    tokens=None,
                )
                if decision.route == "web" and first_error.retryable:
                    raise RouterError(
                        "WEB_UNAVAILABLE",
                        "Web-capable processing is temporarily unavailable.",
                        503,
                        model=decision.model,
                    ) from first_error

                fallback = fallback_for(decision, settings_for_request) if first_error.retryable else None
                if fallback is None:
                    raise

                usage.record_fallback()
                final_decision = fallback
                try:
                    result = await run_in_threadpool(
                        client.chat,
                        model=fallback.model,
                        messages=messages,
                        temperature=payload.temperature,
                        max_tokens=max_tokens,
                    )
                    usage.record_attempt(
                        fallback.model,
                        attempts=result.attempts,
                        failed_attempts=result.attempts - 1,
                        tokens=result.usage.total_tokens,
                    )
                except UpstreamError as fallback_error:
                    usage.record_attempt(
                        fallback.model,
                        attempts=fallback_error.attempts,
                        failed_attempts=fallback_error.attempts,
                        tokens=None,
                    )
                    raise

            usage.finish_request(success=True)
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "chat route=%s model=%s agent=%s latency_ms=%.1f success=true tokens=%s",
                final_decision.route,
                final_decision.model,
                payload.agent.value if payload.agent else "none",
                elapsed_ms,
                result.usage.total_tokens,
            )
            return ChatResponse(
                answer=result.answer,
                model=final_decision.model,
                route=final_decision.route,
                routing_reason=final_decision.reason,
                agent=payload.agent,
                usage=result.usage,
            )
        except Exception:
            usage.finish_request(success=False)
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.warning(
                "chat route=%s model=%s agent=%s latency_ms=%.1f success=false",
                final_decision.route,
                final_decision.model,
                payload.agent.value if payload.agent else "none",
                elapsed_ms,
            )
            raise

    return app


app = create_app()

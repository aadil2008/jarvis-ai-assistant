from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentName(str, Enum):
    JARVIS = "jarvis"
    FRIDAY = "friday"
    EDITH = "edith"


class RouteMode(str, Enum):
    AUTO = "auto"
    FAST = "fast"
    SMART = "smart"
    CODING = "coding"
    WEB = "web"


class ConversationMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(min_length=1)
    agent: AgentName | None = None
    mode: RouteMode = RouteMode.AUTO
    system_prompt: str | None = None
    conversation: list[ConversationMessage] = Field(default_factory=list)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)


class RouteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(min_length=1)
    agent: AgentName | None = None
    mode: RouteMode = RouteMode.AUTO


class UsageInfo(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatResponse(BaseModel):
    success: Literal[True] = True
    answer: str
    model: str
    route: Literal["fast", "smart", "coding", "web"]
    routing_reason: str
    agent: AgentName | None = None
    usage: UsageInfo


class RouteResponse(BaseModel):
    route: Literal["fast", "smart", "coding", "web"]
    model: str
    reason: str


class TranscriptionResponse(BaseModel):
    success: Literal[True] = True
    text: str
    model: str


class ModelListResponse(BaseModel):
    models: list[str]
    cached: bool


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: str
    message: str
    model: str | None = None

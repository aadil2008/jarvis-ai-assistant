from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import Settings
from app.models import AgentName, RouteMode


@dataclass(frozen=True)
class RoutingDecision:
    route: str
    model: str
    reason: str


EXPLICIT_WEB = re.compile(
    r"\b(search|browse|research|look\s*up|find)\b.{0,35}\b(web|internet|online)\b"
    r"|\b(web|internet|online)\b.{0,20}\b(search|research|source|information)\b",
    re.IGNORECASE,
)
RECENCY = re.compile(r"\b(latest|currently|current|today|tonight|recent|recently|this week|as of)\b")
LIVE_DATA = re.compile(
    r"\b(news|weather|forecast|price|stock|score|schedule|traffic|election|"
    r"exchange rate|announcement|release|availability|event|events)\b"
)
CURRENT_LOCAL_CONTEXT = re.compile(r"\b(current (code|function|essay|draft|project|conversation|directory))\b")

STRONG_REASONING = re.compile(
    r"\b(deep|reasoning|deep(?:ly)? analyze|evaluate tradeoffs|architecture|design (?:a|the) system|"
    r"mathematical (?:reasoning|proof)|prove that|investigate|complex reasoning)\b"
)
ANALYSIS_TASK = re.compile(r"\b(analyze|compare|reason|debug|diagnose|synthesize|optimize|calculate)\b")
COMPLEXITY_CONTEXT = re.compile(
    r"\b(complicated|complex|asynchronous|concurrent|distributed|security|scalability|"
    r"algorithm|multiple possibilities|step[- ]by[- ]step|root cause)\b"
)
SIMPLE_TASK = re.compile(
    r"\b(hello|hi|hey|rewrite|summarize|grammar|format|brainstorm|classify|"
    r"short explanation|explain simply)\b"
)
CODE_ACTION = re.compile(
    r"\b(write|build|implement|create|fix|debug|refactor|review|test|compile|deploy|code)\b"
)
CODE_OBJECT = re.compile(
    r"\b(code|coding|program|programming|script|function|class|method|api|endpoint|"
    r"database|query|bug|stack trace|compiler|repository|algorithm|frontend|backend)\b"
)
PROGRAMMING_LANGUAGE = re.compile(
    r"\b(python|javascript|typescript|java|c\+\+|c#|rust|go|swift|kotlin|sql|html|css|"
    r"react|fastapi|django|flask|node(?:\.js)?|bash|shell)\b"
)
CODE_FILE = re.compile(
    r"\b[\w-]+\.(?:py|js|jsx|ts|tsx|java|cpp|c|cs|rs|go|swift|kt|sql|html|css|sh)\b"
)


def _model_for(route: str, settings: Settings) -> str:
    return {
        "fast": settings.fast_model,
        "smart": settings.smart_model,
        "coding": settings.coding_model,
        "web": settings.web_model,
    }[route]


def _web_score(message: str) -> int:
    lowered = message.casefold()
    if CURRENT_LOCAL_CONTEXT.search(lowered):
        return 0
    score = 0
    if EXPLICIT_WEB.search(lowered):
        score += 3
    if re.match(r"^\s*(search|look\s*up|browse)\b", lowered):
        score += 3
    if RECENCY.search(lowered):
        score += 1
    if LIVE_DATA.search(lowered):
        score += 2
    if re.search(r"\b(current price|current news|find online|visit (?:a )?website)\b", lowered):
        score += 3
    if RECENCY.search(lowered) and re.search(
        r"\b(information|status|update|version|who|leader|leadership)\b", lowered
    ):
        score += 2
    return score


def _reasoning_score(message: str, agent: AgentName | None) -> int:
    lowered = message.casefold()
    score = 0
    if STRONG_REASONING.search(lowered):
        score += 3
    if ANALYSIS_TASK.search(lowered):
        score += 2
    if COMPLEXITY_CONTEXT.search(lowered):
        score += 1
    if len(message) > 600:
        score += 1
    if len(message) > 1_500:
        score += 1
    if "```" in message and re.search(r"\b(debug|fix|review|architecture)\b", lowered):
        score += 2

    if agent == AgentName.FRIDAY and re.search(r"\b(research paper|technical analysis)\b", lowered):
        score += 2
    elif agent == AgentName.EDITH and re.search(r"\b(calculate|calculation|deeper analysis)\b", lowered):
        score += 2
    elif agent == AgentName.JARVIS and re.search(r"\b(plan|planning|reasoning)\b", lowered):
        score += 1
    return score


def _coding_score(message: str) -> int:
    lowered = message.casefold()
    score = 0
    if "```" in message or CODE_FILE.search(lowered):
        score += 3
    if re.search(r"\b(coding|programming|software development)\b", lowered):
        score += 3
    if CODE_ACTION.search(lowered) and CODE_OBJECT.search(lowered):
        score += 3
    if PROGRAMMING_LANGUAGE.search(lowered) and (
        CODE_ACTION.search(lowered) or CODE_OBJECT.search(lowered)
    ):
        score += 2
    if re.search(r"\b(debug|stack trace|syntax error|runtime error|unit test)\b", lowered):
        score += 2
    return score


def route_request(
    message: str,
    agent: AgentName | None,
    mode: RouteMode,
    settings: Settings,
) -> RoutingDecision:
    """Select a configured model using transparent, deterministic signals."""
    if mode != RouteMode.AUTO:
        route = mode.value
        return RoutingDecision(
            route=route,
            model=_model_for(route, settings),
            reason=f"Client explicitly selected {route} mode",
        )

    if _web_score(message) >= 3:
        return RoutingDecision(
            route="web",
            model=settings.web_model,
            reason="Request requires current or external web information",
        )

    if _coding_score(message) >= 3:
        return RoutingDecision(
            route="coding",
            model=settings.coding_model,
            reason="Request is a programming or software-development task",
        )

    if _reasoning_score(message, agent) >= 2:
        return RoutingDecision(
            route="smart",
            model=settings.smart_model,
            reason="Request needs deeper reasoning or analysis",
        )

    reason = "Simple or straightforward request"
    if SIMPLE_TASK.search(message.casefold()):
        reason = "Simple conversational or transformation request"
    return RoutingDecision(route="fast", model=settings.fast_model, reason=reason)

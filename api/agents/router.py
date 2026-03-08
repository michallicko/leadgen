"""Message router for 3-tier agent architecture (BL-1010).

Routes incoming messages to the appropriate tier:
  - chat: Simple queries handled by Haiku (fast, cheap)
  - planner: Complex strategy work handled by Sonnet (powerful, slower)
  - planner_interrupt: Message for an already-active planner session

Routing priority:
  1. Active planner check (always wins)
  2. Keyword fast path (~60% of messages, no LLM call)
  3. Haiku classification (~40% of messages, <500ms)
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


@dataclass
class RouteDecision:
    """Result of message routing."""

    target: Literal["chat", "planner", "planner_interrupt"]
    reason: str
    plan_id: str | None = None


# ---------------------------------------------------------------------------
# Keyword patterns for deterministic routing
# ---------------------------------------------------------------------------

# Data lookups -> chat tier
_DATA_PREFIXES = (
    "how many",
    "show me",
    "list",
    "count",
    "what's in",
    "who is",
    "what is the",
    "get me",
)

# Simple greetings -> chat tier
_GREETINGS = frozenset(
    ["hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "sure", "yes", "no"]
)

# Explicit planning commands -> planner
_PLANNER_PREFIXES = (
    "build",
    "create",
    "generate",
    "write",
    "rethink",
    "improve",
    "update",
    "refine",
    "score",
    "analyze",
    "research",
    "draft",
)

# Escalation signals for handle_escalation
_ESCALATION_SIGNALS = (
    "that's wrong",
    "not right",
    "actually",
    "can you really",
    "not helpful",
    "try again",
    "do better",
    "more detail",
    "that's not what i",
    "no, i meant",
    "i need more",
    "go deeper",
)


def route_message(
    message: str,
    page_context: str,
    thread_id: str,
    tenant_context: dict,
    state: dict,
) -> RouteDecision:
    """Decide where a message should go.

    Priority:
      1. If planner is active -> planner_interrupt (always)
      2. Keyword fast path -> deterministic routing (~60%)
      3. Haiku classification -> chat vs planner (~40%)

    Args:
        message: User message text.
        page_context: Current UI page (playbook, contacts, etc.).
        thread_id: Conversation thread identifier.
        tenant_context: Tenant metadata (company_name, domain, namespace).
        state: Session state (has_strategy, onboarding_completed, etc.).

    Returns:
        RouteDecision with target tier and reason.
    """
    # 1. Check if planner is active for this thread
    try:
        from .planner_bridge import get_active_plan

        active = get_active_plan(thread_id)
        if active is not None:
            return RouteDecision(
                target="planner_interrupt",
                reason="active_plan",
                plan_id=active.get("plan_id"),
            )
    except ImportError:
        # planner_bridge not yet available (BL-1009 in progress)
        pass

    # 2. Keyword fast path
    decision = _keyword_route(message, page_context)
    if decision is not None:
        logger.info(
            "Router keyword match: '%s' -> %s (%s)",
            message[:60],
            decision.target,
            decision.reason,
        )
        return decision

    # 3. Haiku classification for ambiguous messages
    decision = _haiku_classify(message, page_context, tenant_context, state)
    logger.info(
        "Router Haiku classified: '%s' -> %s (%s)",
        message[:60],
        decision.target,
        decision.reason,
    )
    return decision


def _keyword_route(message: str, page_context: str) -> RouteDecision | None:
    """Attempt deterministic keyword-based routing.

    Returns None if the message is ambiguous and needs LLM classification.
    """
    lower = message.lower().strip()

    # Simple greetings -> chat tier (checked before length to catch "hi", "ok")
    if lower in _GREETINGS:
        return RouteDecision(target="chat", reason="greeting")

    # Very short messages -> chat
    if len(lower) < 4:
        return RouteDecision(target="chat", reason="short_message")

    # Data lookups -> chat tier
    if any(lower.startswith(p) for p in _DATA_PREFIXES):
        return RouteDecision(target="chat", reason="data_lookup_keyword")

    # Explicit strategy/planning commands -> planner
    if any(lower.startswith(p) for p in _PLANNER_PREFIXES):
        return RouteDecision(target="planner", reason="planning_keyword")

    # Domain input (e.g. "unitedarts.cz") -> planner (likely onboarding)
    if "." in message and len(message.split()) <= 5 and not message.startswith("http"):
        # Simple heuristic: short text with a dot that looks like a domain
        if re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", message.strip()):
            return RouteDecision(target="planner", reason="domain_input")

    # Help requests -> chat tier
    if "help" in lower or "how do i" in lower or lower.startswith("what can"):
        return RouteDecision(target="chat", reason="help_request")

    # Question marks on short messages -> chat tier
    if lower.endswith("?") and len(lower.split()) <= 10:
        return RouteDecision(target="chat", reason="short_question")

    return None  # Ambiguous -> fall through to Haiku


def _haiku_classify(
    message: str,
    page_context: str,
    tenant_context: dict,
    state: dict,
) -> RouteDecision:
    """Use Haiku to classify ambiguous messages.

    Fast (<500ms) classification into chat vs planner.
    Defaults to chat if classification fails or times out.
    """
    has_strategy = state.get("has_strategy", False)

    system = (
        "You are a message router. Classify the user's message into one of two categories:\n\n"
        "CHAT: Simple questions, data lookups, greetings, help requests, quick answers, "
        "status checks, navigation help.\n"
        "PLANNER: Strategy work, research requests, content generation, complex analysis, "
        "multi-step tasks, document editing, ICP/persona work.\n\n"
        "Current page: {page}\n"
        "User has strategy: {has_strategy}\n\n"
        "Respond with exactly one word: CHAT or PLANNER"
    ).format(page=page_context or "unknown", has_strategy=has_strategy)

    start = time.monotonic()

    try:
        model = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            temperature=0.0,
            max_tokens=10,
            timeout=2.0,
        )

        response = model.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=message),
            ]
        )

        elapsed_ms = (time.monotonic() - start) * 1000

        raw = (
            response.content.strip().upper()
            if isinstance(response.content, str)
            else ""
        )
        # Clean to just CHAT or PLANNER
        raw = re.sub(r"[^A-Z]", "", raw)

        if raw == "PLANNER":
            target = "planner"
        else:
            target = "chat"

        logger.info(
            "Haiku route classification: '%s' -> %s (%.0fms)",
            message[:60],
            target,
            elapsed_ms,
        )

        return RouteDecision(
            target=target,
            reason="haiku_classification",
        )

    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.warning(
            "Haiku route classification failed (%.0fms): %s — defaulting to chat",
            elapsed_ms,
            exc,
        )
        return RouteDecision(target="chat", reason="haiku_fallback")


def handle_escalation(message: str, thread_id: str) -> RouteDecision:
    """Detect user dissatisfaction and escalate to planner if needed.

    Called after a chat tier response to check if the user wants
    something more substantial.

    Args:
        message: User's follow-up message.
        thread_id: Conversation thread identifier.

    Returns:
        RouteDecision — planner if escalation detected, chat otherwise.
    """
    lower = message.lower()
    if any(signal in lower for signal in _ESCALATION_SIGNALS):
        return RouteDecision(target="planner", reason="escalation")
    return RouteDecision(target="chat", reason="no_escalation")

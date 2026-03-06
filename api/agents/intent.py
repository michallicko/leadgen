"""Intent classification for the orchestrator.

Uses Haiku for fast (<500ms) classification of user messages into
intent categories. The classifier uses a minimal prompt and structured
output parsing. Copilot is the default fallback for simple queries.

Intent categories:
  - strategy_edit: Strategy document editing
  - research: Web search, market analysis
  - enrichment: Contact/company enrichment operations
  - outreach: Message generation, campaign management
  - copilot: Quick questions, help, data lookups (default fallback)
"""

from __future__ import annotations

import logging
import re
import time

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

# Valid intent categories
VALID_INTENTS = frozenset(
    [
        "strategy_edit",
        "research",
        "enrichment",
        "outreach",
        "copilot",
    ]
)

# Default intent when classification fails — copilot handles simple queries
DEFAULT_INTENT = "copilot"

# Intent classification prompt (~120 tokens)
INTENT_CLASSIFICATION_PROMPT = """Classify the user's message into exactly one category:

- strategy_edit: Writing, updating, reviewing, or generating strategy document sections. Includes ICP tiers, buyer personas, and section completeness checks.
- research: Web search, company research, market analysis, enrichment analysis.
- enrichment: Running enrichment pipeline, enriching contacts/companies, checking enrichment status, triggering L1/L2/person enrichment.
- outreach: Message generation, outreach planning, campaign management, creating email sequences, writing personalized messages.
- copilot: Simple questions, status checks, greetings, help requests, data lookups, "how do I" questions, clarifications.

Respond with ONLY the category name. No explanation, no punctuation."""

# Keyword-based fast path for obvious intents (avoids LLM call)
STRATEGY_KEYWORDS = [
    "write section",
    "update section",
    "generate strategy",
    "executive summary",
    "value proposition",
    "competitive positioning",
    "channel strategy",
    "messaging framework",
    "metrics",
    "kpi",
    "action plan",
    "icp tier",
    "buyer persona",
    "set persona",
    "draft the",
    "fill in the",
    "complete the section",
]

RESEARCH_KEYWORDS = [
    "search for",
    "research",
    "look up",
    "find information",
    "web search",
    "market analysis",
    "competitor",
]

ENRICHMENT_KEYWORDS = [
    "enrich",
    "enrichment",
    "run pipeline",
    "trigger enrichment",
    "l1 enrichment",
    "l2 enrichment",
    "person enrichment",
    "enrichment status",
]

OUTREACH_KEYWORDS = [
    "generate message",
    "write outreach",
    "create campaign",
    "outreach",
    "send message",
    "campaign",
    "email sequence",
    "write email",
    "personalize message",
]


def classify_intent_fast(message: str) -> str | None:
    """Attempt keyword-based classification without an LLM call.

    Returns the intent string if a keyword match is found,
    or None if the message needs LLM classification.
    """
    lower = message.lower().strip()

    # Very short messages are copilot
    if len(lower) < 10:
        return "copilot"

    # Greetings
    if lower in ("hi", "hello", "hey", "thanks", "thank you", "ok", "okay"):
        return "copilot"

    for kw in STRATEGY_KEYWORDS:
        if kw in lower:
            return "strategy_edit"

    for kw in ENRICHMENT_KEYWORDS:
        if kw in lower:
            return "enrichment"

    for kw in OUTREACH_KEYWORDS:
        if kw in lower:
            return "outreach"

    for kw in RESEARCH_KEYWORDS:
        if kw in lower:
            return "research"

    return None


def classify_intent(message: str) -> tuple[str, float]:
    """Classify user message intent using Haiku.

    Args:
        message: The user's message text.

    Returns:
        Tuple of (intent_category, latency_ms).
    """
    # Try fast path first
    fast_result = classify_intent_fast(message)
    if fast_result is not None:
        return fast_result, 0.0

    # LLM-based classification
    start = time.monotonic()

    try:
        model = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            temperature=0.0,
            max_tokens=20,
        )

        response = model.invoke(
            [
                SystemMessage(content=INTENT_CLASSIFICATION_PROMPT),
                HumanMessage(content=message),
            ]
        )

        elapsed_ms = (time.monotonic() - start) * 1000

        # Parse the response
        raw = (
            response.content.strip().lower()
            if isinstance(response.content, str)
            else ""
        )
        # Clean up any punctuation or extra text
        raw = re.sub(r"[^a-z_]", "", raw)

        if raw in VALID_INTENTS:
            intent = raw
        else:
            logger.warning(
                "Intent classifier returned invalid category '%s', defaulting to '%s'",
                raw,
                DEFAULT_INTENT,
            )
            intent = DEFAULT_INTENT

        logger.info(
            "Intent classified: '%s' -> %s (%.0fms)",
            message[:80],
            intent,
            elapsed_ms,
        )

        return intent, elapsed_ms

    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.exception("Intent classification failed: %s", exc)
        return DEFAULT_INTENT, elapsed_ms

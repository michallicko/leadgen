"""Intent classification for the orchestrator.

Uses Haiku for fast (<500ms) classification of user messages into
one of five intent categories: strategy_edit, research, quick_answer,
campaign, or outreach. The classifier uses a minimal prompt and structured
output parsing.
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
        "quick_answer",
        "campaign",
        "outreach",
    ]
)

# Default intent when classification fails
DEFAULT_INTENT = "quick_answer"

# Intent classification prompt (~120 tokens)
INTENT_CLASSIFICATION_PROMPT = """Classify the user's message into exactly one category:

- strategy_edit: Writing, updating, reviewing, or generating strategy document sections. Includes ICP tiers, buyer personas, and section completeness checks.
- research: Web search, company research, market analysis, contact/company data queries, enrichment analysis.
- quick_answer: Simple questions, status checks, greetings, clarifications, or questions about existing strategy content.
- campaign: Campaign management, campaign creation, campaign analytics, contact filtering for campaigns.
- outreach: Message generation, writing outreach messages, personalizing messages, A/B variants, message templates, reviewing or approving messages.

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
    "how many contacts",
    "how many companies",
    "list contacts",
    "count contacts",
    "count companies",
    "analyze enrichment",
    "market analysis",
    "competitor",
]

OUTREACH_KEYWORDS = [
    "generate message",
    "write message",
    "write a message",
    "write outreach",
    "personalize message",
    "message for",
    "draft message",
    "outreach message",
    "linkedin message",
    "email message",
    "message template",
    "a/b variant",
    "ab variant",
    "message variant",
    "approve message",
    "reject message",
    "review message",
]

CAMPAIGN_KEYWORDS = [
    "create campaign",
    "campaign analytics",
    "campaign performance",
    "filter contacts for",
    "send campaign",
    "email sequence",
    "launch campaign",
]


def classify_intent_fast(message: str) -> str | None:
    """Attempt keyword-based classification without an LLM call.

    Returns the intent string if a keyword match is found,
    or None if the message needs LLM classification.
    """
    lower = message.lower().strip()

    # Very short messages are quick answers
    if len(lower) < 10:
        return "quick_answer"

    # Greetings
    if lower in ("hi", "hello", "hey", "thanks", "thank you", "ok", "okay"):
        return "quick_answer"

    for kw in STRATEGY_KEYWORDS:
        if kw in lower:
            return "strategy_edit"

    for kw in RESEARCH_KEYWORDS:
        if kw in lower:
            return "research"

    # Check outreach BEFORE campaign (more specific)
    for kw in OUTREACH_KEYWORDS:
        if kw in lower:
            return "outreach"

    for kw in CAMPAIGN_KEYWORDS:
        if kw in lower:
            return "campaign"

    return None


def classify_intent(message: str) -> tuple[str, float]:
    """Classify user message intent using Haiku.

    Args:
        message: The user's message text.

    Returns:
        Tuple of (intent_category, latency_ms).
        intent_category is one of: strategy_edit, research, quick_answer,
        campaign, outreach.
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

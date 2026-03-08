"""Classify user interruptions during plan execution (BL-1018).

Two-stage classification: keyword fast path for clear cases,
Haiku LLM fallback for ambiguous messages. The classifier returns
a structured InterruptClassification with type, confidence, and
extracted info specific to the interrupt type.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

InterruptType = Literal["correction", "stop", "question", "redirect"]


@dataclass
class InterruptClassification:
    """Structured result from interrupt classification."""

    type: InterruptType
    confidence: float  # 0-1
    extracted_info: dict = field(default_factory=dict)

    # extracted_info examples by type:
    # correction: {"correction": "we don't do festivals", "affects": ["company_profile", "icp"]}
    # stop: {"reason": "this is wrong"}
    # question: {"question": "what did you find so far?"}
    # redirect: {"new_focus": "DACH market", "phase_hint": "research_market"}


# ---------------------------------------------------------------------------
# Haiku classification prompt
# ---------------------------------------------------------------------------

INTERRUPT_CLASSIFICATION_PROMPT = """You are classifying a user message that interrupted an AI agent's plan execution.

The agent is currently in the "{current_phase}" phase of a strategy plan.

Classify the message into exactly one category:

- correction: The user is correcting a fact or assumption the agent made (e.g., "we don't do festivals", "that's wrong", "actually we pivoted to B2B")
- stop: The user wants to halt/pause execution (e.g., "stop", "wait", "hold on", "cancel")
- question: The user is asking a question about progress or results (e.g., "what did you find?", "how far along are you?")
- redirect: The user wants to change focus or skip ahead (e.g., "focus on DACH market", "skip to strategy", "let's do competitors instead")

Respond with ONLY a JSON object (no markdown, no explanation):
{{"type": "<category>", "extracted_info": {{<relevant extracted data>}}}}

For corrections, include: {{"correction": "<what they said>", "affects": [<list of potentially affected areas>]}}
For stops, include: {{"reason": "<why they stopped>"}}
For questions, include: {{"question": "<the question>"}}
For redirects, include: {{"new_focus": "<what they want to focus on>", "phase_hint": "<best matching phase or empty>"}}"""


# ---------------------------------------------------------------------------
# Keyword fast path
# ---------------------------------------------------------------------------

# Stop patterns — must be at start of message
_STOP_PREFIXES = [
    "stop",
    "wait",
    "hold on",
    "pause",
    "cancel",
    "abort",
    "halt",
    "don't",
    "do not",
]

# Correction signals — can appear anywhere
_CORRECTION_SIGNALS = [
    "that's wrong",
    "that's not right",
    "that is wrong",
    "that is not right",
    "actually we",
    "we don't",
    "we do not",
    "no, we",
    "incorrect",
    "not anymore",
    "we stopped",
    "we pivoted",
    "wrong about",
    "not true",
    "that's incorrect",
]

# Question signals — at start or ending with ?
_QUESTION_PREFIXES = [
    "what",
    "how",
    "why",
    "when",
    "where",
    "who",
    "can you",
    "did you",
    "show me",
    "tell me",
    "have you",
]

# Redirect signals — can appear anywhere
_REDIRECT_SIGNALS = [
    "instead",
    "focus on",
    "switch to",
    "let's do",
    "skip to",
    "move to",
    "actually focus",
    "jump to",
    "go to",
    "prioritize",
    "let's skip",
]


def _keyword_classify(message: str) -> InterruptClassification | None:
    """Keyword-based classification for clear cases.

    Returns an InterruptClassification if a clear match is found,
    or None if the message is ambiguous and needs LLM classification.
    """
    lower = message.lower().strip()

    if not lower:
        return InterruptClassification(
            type="correction",
            confidence=0.5,
            extracted_info={"correction": message},
        )

    # Stop signals (must be at start)
    for prefix in _STOP_PREFIXES:
        if lower.startswith(prefix):
            return InterruptClassification(
                type="stop",
                confidence=0.9,
                extracted_info={"reason": message},
            )

    # Strong corrections (anywhere in message)
    for signal in _CORRECTION_SIGNALS:
        if signal in lower:
            return InterruptClassification(
                type="correction",
                confidence=0.9,
                extracted_info={"correction": message},
            )

    # Questions (ending with ? or starting with question word)
    if lower.endswith("?") or any(lower.startswith(p) for p in _QUESTION_PREFIXES):
        return InterruptClassification(
            type="question",
            confidence=0.85,
            extracted_info={"question": message},
        )

    # Redirects (anywhere in message)
    for signal in _REDIRECT_SIGNALS:
        if signal in lower:
            return InterruptClassification(
                type="redirect",
                confidence=0.85,
                extracted_info={"new_focus": message},
            )

    return None  # Ambiguous — needs LLM


# ---------------------------------------------------------------------------
# Haiku LLM fallback
# ---------------------------------------------------------------------------

_VALID_TYPES = frozenset(["correction", "stop", "question", "redirect"])


def _haiku_classify(
    message: str, current_phase: str, plan_context: dict
) -> InterruptClassification:
    """Use Haiku for ambiguous interrupt classification.

    Falls back to correction (safest assumption) if Haiku fails
    or returns an unparseable response.
    """
    start = time.monotonic()

    try:
        model = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            temperature=0.0,
            max_tokens=200,
        )

        prompt = INTERRUPT_CLASSIFICATION_PROMPT.format(current_phase=current_phase)

        response = model.invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=message),
            ]
        )

        elapsed_ms = (time.monotonic() - start) * 1000

        raw = response.content.strip() if isinstance(response.content, str) else ""

        # Parse JSON response
        import json

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from response if wrapped in markdown
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
            else:
                logger.warning(
                    "Haiku interrupt classifier returned unparseable: '%s'", raw[:200]
                )
                return InterruptClassification(
                    type="correction",
                    confidence=0.5,
                    extracted_info={"correction": message},
                )

        itype = parsed.get("type", "correction")
        if itype not in _VALID_TYPES:
            logger.warning(
                "Haiku returned invalid type '%s', defaulting to correction", itype
            )
            itype = "correction"

        extracted = parsed.get("extracted_info", {})
        if not isinstance(extracted, dict):
            extracted = {}

        logger.info(
            "Interrupt classified by Haiku: type=%s (%.0fms)", itype, elapsed_ms
        )

        return InterruptClassification(
            type=itype,
            confidence=0.75,
            extracted_info=extracted,
        )

    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.exception(
            "Haiku interrupt classification failed (%.0fms): %s", elapsed_ms, exc
        )
        # Safe default: treat as correction so plan continues
        return InterruptClassification(
            type="correction",
            confidence=0.5,
            extracted_info={"correction": message},
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_interrupt(
    message: str, current_phase: str, plan_context: dict
) -> InterruptClassification:
    """Classify a user message that arrived during plan execution.

    Two-stage: keyword fast path + Haiku LLM for ambiguous.

    Args:
        message: The user's interrupt message.
        current_phase: Current plan phase being executed.
        plan_context: Plan config dict for additional context.

    Returns:
        InterruptClassification with type, confidence, and extracted info.
    """
    # Stage 1: Keyword patterns (fast, deterministic)
    result = _keyword_classify(message)
    if result and result.confidence > 0.8:
        logger.info(
            "Interrupt classified by keywords: type=%s, confidence=%.2f",
            result.type,
            result.confidence,
        )
        return result

    # Stage 2: Haiku classification (for ambiguous messages)
    return _haiku_classify(message, current_phase, plan_context)

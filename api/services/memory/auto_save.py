"""Auto-detect and save important decisions from conversations.

Analyzes conversation messages to identify decisions, preferences, insights,
and constraints that should be persisted to long-term memory for future sessions.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns that indicate important decisions/preferences
DECISION_PATTERNS = [
    r"\b(?:i (?:want|need|prefer|decide|chose|approved?|agree|confirm))\b",
    r"\b(?:let'?s (?:go with|use|do|try|focus on|stick with))\b",
    r"\b(?:yes,? (?:that'?s|do it|go ahead|perfect|exactly|correct))\b",
    r"\b(?:no,? (?:don'?t|not that|skip|remove|ignore))\b",
    r"\b(?:our (?:target|focus|priority|strategy|approach) (?:is|should be))\b",
    r"\b(?:we (?:should|must|need to|will|are going to))\b",
]

CONSTRAINT_PATTERNS = [
    r"\b(?:budget (?:is|of|around|limit))\b",
    r"\b(?:deadline|timeline|by (?:end of|next|this))\b",
    r"\b(?:don'?t (?:contact|include|target|send))\b",
    r"\b(?:must (?:have|include|be))\b",
    r"\b(?:only (?:in|for|target|focus))\b",
    r"\b(?:(?:exclude|avoid|never|not interested in))\b",
]

PREFERENCE_PATTERNS = [
    r"\b(?:i (?:like|prefer|always|usually))\b",
    r"\b(?:tone (?:should be|of))\b",
    r"\b(?:(?:formal|casual|professional|friendly) (?:tone|style))\b",
    r"\b(?:language:? (?:english|german|czech))\b",
]

# Minimum length for content to be considered saveable
MIN_CONTENT_LENGTH = 20

# Content types mapped to patterns
PATTERN_TYPE_MAP = [
    (DECISION_PATTERNS, "decision"),
    (CONSTRAINT_PATTERNS, "constraint"),
    (PREFERENCE_PATTERNS, "preference"),
]


def detect_saveable_content(message: str, role: str = "user") -> Optional[dict]:
    """Analyze a message to detect content worth saving to long-term memory.

    Only user messages are analyzed (assistant messages are responses, not decisions).

    Args:
        message: The message text to analyze.
        role: The role of the message sender.

    Returns:
        {"content": str, "content_type": str, "confidence": float}
        or None if nothing worth saving is detected.
    """
    if role != "user":
        return None

    if not message or len(message.strip()) < MIN_CONTENT_LENGTH:
        return None

    message_lower = message.lower()

    # Check each pattern type
    best_match = None
    best_confidence = 0.0

    for patterns, content_type in PATTERN_TYPE_MAP:
        match_count = 0
        for pattern in patterns:
            if re.search(pattern, message_lower):
                match_count += 1

        if match_count > 0:
            # Confidence based on number of pattern matches
            confidence = min(0.9, 0.3 + (match_count * 0.2))
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = {
                    "content": message.strip(),
                    "content_type": content_type,
                    "confidence": round(confidence, 2),
                }

    return best_match


def auto_save_from_conversation(
    tenant_id: str,
    messages: list[dict],
    user_id: Optional[str] = None,
    min_confidence: float = 0.5,
) -> list[dict]:
    """Scan conversation messages and auto-save important ones to memory.

    Args:
        tenant_id: Tenant UUID for isolation.
        messages: List of message dicts with 'role', 'content', and optionally 'id'.
        user_id: Optional user UUID.
        min_confidence: Minimum confidence threshold to save.

    Returns:
        List of saved memory entries.
    """
    from .embeddings import save_memory

    saved = []

    for msg in messages:
        detection = detect_saveable_content(
            msg.get("content", ""),
            msg.get("role", "user"),
        )

        if detection and detection["confidence"] >= min_confidence:
            memory = save_memory(
                tenant_id=tenant_id,
                content=detection["content"],
                content_type=detection["content_type"],
                user_id=user_id,
                metadata={
                    "auto_saved": True,
                    "confidence": detection["confidence"],
                },
                source_message_id=msg.get("id"),
            )
            if memory:
                saved.append(memory.to_dict())

    return saved


def should_auto_save(message: str, role: str = "user") -> bool:
    """Quick check if a message might be worth auto-saving.

    Lighter than detect_saveable_content — used to avoid unnecessary processing.
    """
    if role != "user" or not message or len(message) < MIN_CONTENT_LENGTH:
        return False

    message_lower = message.lower()
    # Quick keyword check
    keywords = [
        "decide",
        "prefer",
        "approve",
        "agree",
        "confirm",
        "go with",
        "let's",
        "budget",
        "deadline",
        "must",
        "don't",
        "exclude",
        "avoid",
        "focus on",
    ]
    return any(kw in message_lower for kw in keywords)

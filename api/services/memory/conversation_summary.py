"""Conversation summarization with sliding window compaction.

When a conversation exceeds a threshold (default: 15 messages), the oldest
messages are summarized into a compact representation (~200 tokens) that
preserves decisions, strategies, constraints, and preferences.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Summarization thresholds
MESSAGE_THRESHOLD = 15  # Trigger summarization when messages exceed this
SUMMARIZE_COUNT = 10  # Number of oldest messages to summarize
TARGET_SUMMARY_TOKENS = 200
RE_SUMMARIZE_GROWTH = 15  # Re-summarize when messages grow past threshold again


def should_summarize(message_count: int, has_existing_summary: bool) -> bool:
    """Check if conversation should be summarized.

    Args:
        message_count: Current number of unsummarized messages.
        has_existing_summary: Whether a previous summary exists.

    Returns:
        True if summarization should trigger.
    """
    if has_existing_summary:
        # Re-summarize when messages grow past threshold again
        return message_count > RE_SUMMARIZE_GROWTH
    return message_count > MESSAGE_THRESHOLD


def summarize_messages(
    messages: list[dict],
    existing_summary: Optional[str] = None,
    count: int = SUMMARIZE_COUNT,
) -> Optional[str]:
    """Summarize the oldest N messages into a compact representation.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
        existing_summary: Previous summary to incorporate.
        count: Number of oldest messages to summarize.

    Returns:
        Summary string (~200 tokens), or None if summarization fails.
    """
    if not messages:
        return existing_summary

    to_summarize = messages[:count]
    if not to_summarize:
        return existing_summary

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, using fallback summarization")
        return _fallback_summarize(to_summarize, existing_summary)

    prompt = _build_conversation_summary_prompt(to_summarize, existing_summary)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=TARGET_SUMMARY_TOKENS * 2,
            messages=[{"role": "user", "content": prompt}],
        )

        summary = response.content[0].text if response.content else None
        return summary

    except Exception:
        logger.exception("Conversation summarization failed")
        return _fallback_summarize(to_summarize, existing_summary)


def compact_conversation(
    messages: list[dict],
    existing_summary: Optional[str] = None,
) -> dict:
    """Compact a conversation by summarizing old messages.

    Returns the compacted state: summary + remaining messages.

    Args:
        messages: Full list of conversation messages.
        existing_summary: Previous summary if any.

    Returns:
        {
            "summary": str,           # New combined summary
            "messages": list[dict],    # Remaining unsummarized messages
            "summarized_count": int,   # How many messages were summarized
        }
    """
    msg_count = len(messages)
    has_summary = existing_summary is not None

    if not should_summarize(msg_count, has_summary):
        return {
            "summary": existing_summary,
            "messages": messages,
            "summarized_count": 0,
        }

    # Summarize oldest messages
    to_summarize = messages[:SUMMARIZE_COUNT]
    remaining = messages[SUMMARIZE_COUNT:]

    new_summary = summarize_messages(to_summarize, existing_summary)

    return {
        "summary": new_summary,
        "messages": remaining,
        "summarized_count": len(to_summarize),
    }


def format_summary_for_context(summary: str) -> str:
    """Format a conversation summary for injection into agent context.

    Wraps the summary in a clear marker so the agent knows it's a summary.
    """
    return (
        "[Conversation Summary - Earlier in this conversation, "
        "the following was discussed and decided:]\n{}\n"
        "[End of Summary - Current conversation continues below]"
    ).format(summary)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_conversation_summary_prompt(
    messages: list[dict],
    existing_summary: Optional[str],
) -> str:
    """Build the prompt for conversation summarization."""
    context = ""
    if existing_summary:
        context = (
            "Previous conversation summary:\n{}\n\n"
            "Now summarize the following additional messages, "
            "incorporating the previous summary:\n\n"
        ).format(existing_summary)

    formatted = []
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        # Truncate very long messages
        if len(content) > 1000:
            content = content[:1000] + "..."
        formatted.append("{}: {}".format(role, content))

    conversation_text = "\n".join(formatted)

    return (
        "{}Summarize this conversation in approximately {} words. "
        "You MUST preserve:\n"
        "- User decisions and approvals\n"
        "- Approved strategies or approaches\n"
        "- Rejected suggestions (what the user said no to)\n"
        "- Key constraints or requirements stated by the user\n"
        "- User preferences (tone, focus areas, industries)\n\n"
        "You MUST omit:\n"
        "- Filler and pleasantries\n"
        "- Intermediate drafts\n"
        "- Tool execution details\n"
        "- Verbose explanations already captured in decisions\n\n"
        "Conversation:\n{}"
    ).format(context, TARGET_SUMMARY_TOKENS, conversation_text)


def _fallback_summarize(
    messages: list[dict],
    existing_summary: Optional[str],
) -> str:
    """Generate a basic summary without LLM calls.

    Extracts user messages and creates a condensed list.
    """
    parts = []
    if existing_summary:
        parts.append("Previous: {}".format(existing_summary[:300]))

    user_messages = [
        m.get("content", "")[:200] for m in messages if m.get("role") == "user"
    ]

    if user_messages:
        parts.append("User discussed: {}".format("; ".join(user_messages[:5])))

    return " | ".join(parts) if parts else "No significant decisions recorded."

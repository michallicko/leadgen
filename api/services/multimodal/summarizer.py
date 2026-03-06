"""LLM-based content summarization for extracted documents.

Generates concise summaries (~500 tokens) from extracted text for injection
into agent context at L1 detail level.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Target summary length
TARGET_SUMMARY_TOKENS = 500
MAX_INPUT_CHARS = 100_000  # ~25K tokens - truncate beyond this


def summarize_content(
    text: str,
    filename: str = "",
    max_tokens: int = TARGET_SUMMARY_TOKENS,
) -> Optional[str]:
    """Summarize extracted content using Claude.

    Args:
        text: The full extracted text to summarize.
        filename: Original filename for context.
        max_tokens: Target summary length in tokens.

    Returns:
        Summary string, or None if summarization fails.
    """
    if not text or len(text.strip()) < 50:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping summarization")
        return _fallback_summary(text, filename)

    # Truncate very long texts
    input_text = text[:MAX_INPUT_CHARS]
    if len(text) > MAX_INPUT_CHARS:
        input_text += "\n\n[... content truncated for summarization ...]"

    prompt = _build_summary_prompt(input_text, filename, max_tokens)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens * 2,  # Allow some headroom
            messages=[{"role": "user", "content": prompt}],
        )

        summary = response.content[0].text if response.content else None
        return summary

    except Exception:
        logger.exception("Summarization failed, using fallback")
        return _fallback_summary(text, filename)


def _build_summary_prompt(text: str, filename: str, max_tokens: int) -> str:
    """Build the summarization prompt."""
    file_context = ""
    if filename:
        file_context = ' from the document "{}"'.format(filename)

    return (
        "Summarize the following content{} in approximately {} words. "
        "Focus on:\n"
        "- Key findings and conclusions\n"
        "- Important data points and metrics\n"
        "- Actionable insights\n"
        "- Main topics covered\n\n"
        "Preserve specific names, numbers, and dates. "
        "Format as a concise paragraph, not bullet points.\n\n"
        "Content:\n{}"
    ).format(file_context, max_tokens, text)


def _fallback_summary(text: str, filename: str = "") -> str:
    """Generate a basic summary without LLM (first N characters + stats)."""
    preview = text[:800].strip()
    word_count = len(text.split())
    char_count = len(text)

    parts = []
    if filename:
        parts.append("Document: {}".format(filename))
    parts.append("Length: {} words ({} characters)".format(word_count, char_count))
    parts.append("Preview: {}...".format(preview))

    return "\n".join(parts)


def generate_l0_mention(file_record) -> str:
    """Generate an L0 mention (~20 tokens) for a file upload.

    Used when listing files or referencing them briefly in context.
    """
    size_kb = file_record.size_bytes / 1024
    if size_kb > 1024:
        size_str = "{:.1f}MB".format(size_kb / 1024)
    else:
        size_str = "{:.0f}KB".format(size_kb)

    page_info = ""
    if file_record.contents:
        for c in file_record.contents:
            if c.page_range:
                page_info = ", {} pages".format(
                    c.page_range.split("-")[-1] if "-" in c.page_range else "1"
                )
                break

    return "Uploaded: {} ({}{})".format(
        file_record.original_filename, size_str, page_info
    )

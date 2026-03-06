"""Token budgeting and progressive detail injection for multimodal content.

Manages how extracted document content is injected into agent context:
- L0: mention (~20 tokens) - brief reference
- L1: summary (~500 tokens) - key findings, default injection
- L2: full text (on-demand via tool) - complete content

Total multimodal budget: 8K tokens per agent call.
"""

from __future__ import annotations

import logging
from typing import Optional

from ...models import ExtractedContent, FileUpload, db

logger = logging.getLogger(__name__)

# Token budget for multimodal content per agent call
MAX_MULTIMODAL_TOKENS = 8000

# Detail levels and their typical token ranges
DETAIL_LEVELS = {
    "l0": {"label": "mention", "max_tokens": 30},
    "l1": {"label": "summary", "max_tokens": 600},
    "l2": {"label": "full_text", "max_tokens": None},  # No limit (on-demand)
}


def get_file_context(
    file_id: str,
    detail_level: str = "l1",
    max_tokens: Optional[int] = None,
) -> Optional[dict]:
    """Get file content at the specified detail level.

    Args:
        file_id: UUID of the file upload.
        detail_level: One of 'l0', 'l1', 'l2'.
        max_tokens: Override max tokens for this request.

    Returns:
        {"content": str, "tokens": int, "level": str} or None.
    """
    file_record = db.session.get(FileUpload, file_id)
    if not file_record:
        return None

    if file_record.processing_status != "completed":
        return {
            "content": "[File '{}' is {}]".format(
                file_record.original_filename, file_record.processing_status
            ),
            "tokens": 10,
            "level": "l0",
        }

    if detail_level == "l0":
        from .summarizer import generate_l0_mention

        mention = generate_l0_mention(file_record)
        return {"content": mention, "tokens": len(mention) // 4, "level": "l0"}

    if detail_level == "l1":
        summary = _get_content_by_type(file_id, "summary")
        if summary:
            content = summary.content_summary or summary.content_text or ""
            return {
                "content": content,
                "tokens": summary.token_count or len(content) // 4,
                "level": "l1",
            }
        # Fall back to L0 if no summary
        return get_file_context(file_id, "l0")

    if detail_level == "l2":
        full = _get_content_by_type(file_id, "full_text")
        if full:
            content = full.content_text or ""
            token_count = full.token_count or len(content) // 4
            # Apply max_tokens truncation if specified
            if max_tokens and token_count > max_tokens:
                char_limit = max_tokens * 4
                content = content[:char_limit] + "\n\n[... truncated ...]"
                token_count = max_tokens
            return {
                "content": content,
                "tokens": token_count,
                "level": "l2",
            }
        return get_file_context(file_id, "l1")

    return None


def build_multimodal_context(
    file_ids: list[str],
    budget_tokens: int = MAX_MULTIMODAL_TOKENS,
) -> list[dict]:
    """Build context entries for multiple files within a token budget.

    Distributes the budget proportionally across files, defaulting to L1.
    If total L1 tokens exceed budget, some files get downgraded to L0.

    Args:
        file_ids: List of file UUIDs to include.
        budget_tokens: Total token budget for multimodal content.

    Returns:
        List of {"file_id": str, "content": str, "tokens": int, "level": str}.
    """
    if not file_ids:
        return []

    # First pass: get L1 for all files
    entries = []
    total_tokens = 0

    for fid in file_ids:
        ctx = get_file_context(fid, "l1")
        if ctx:
            entries.append({"file_id": fid, **ctx})
            total_tokens += ctx["tokens"]

    # If within budget, return as-is
    if total_tokens <= budget_tokens:
        return entries

    # Over budget: downgrade least important files to L0
    # Sort by token count descending (biggest files get downgraded first)
    entries.sort(key=lambda e: e["tokens"], reverse=True)

    result = []
    remaining_budget = budget_tokens

    for entry in entries:
        if entry["tokens"] <= remaining_budget:
            result.append(entry)
            remaining_budget -= entry["tokens"]
        else:
            # Downgrade to L0
            l0 = get_file_context(entry["file_id"], "l0")
            if l0:
                result.append({"file_id": entry["file_id"], **l0})
                remaining_budget -= l0["tokens"]

    return result


def _get_content_by_type(file_id: str, content_type: str) -> Optional[ExtractedContent]:
    """Get an ExtractedContent record by file_id and content_type."""
    return ExtractedContent.query.filter_by(
        file_id=file_id, content_type=content_type
    ).first()

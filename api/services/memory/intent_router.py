"""Intent-aware tool routing for phase-filtered tool selection.

Classifies user intent and maps it to a subset of tools, reducing
tool schema tokens from ~2.5K to ~600-1K per agent call.

Uses keyword/heuristic classification (no LLM call needed).
Falls back to full tool set on ambiguity.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Intent -> tool name mapping
# Each phase gets only the tools relevant to that workflow stage
INTENT_TOOL_MAP = {
    "strategy": [
        "get_strategy",
        "save_strategy",
        "get_strategy_feedback",
        "analyze_company_portfolio",
        "analyze_contact_portfolio",
        "count_contacts",
        "count_companies",
        "list_contacts",
        "list_companies",
        "web_search",
        "search_memory",
        "save_insight",
    ],
    "contacts": [
        "count_contacts",
        "count_companies",
        "list_contacts",
        "list_companies",
        "analyze_contact_portfolio",
        "analyze_company_portfolio",
        "search_memory",
        "web_search",
        "save_insight",
    ],
    "messages": [
        "generate_messages",
        "review_messages",
        "search_memory",
        "save_insight",
    ],
    "campaign": [
        "create_campaign",
        "update_campaign",
        "get_campaign_stats",
        "search_memory",
        "web_search",
        "save_insight",
    ],
    "documents": [
        "analyze_document",
        "extract_data",
        "analyze_image",
        "search_memory",
        "save_insight",
    ],
}

# Intent classification keywords (checked against lowered message)
INTENT_KEYWORDS = {
    "strategy": [
        r"\b(?:strategy|icp|ideal customer|target market|positioning)\b",
        r"\b(?:value proposition|competitive|differentiator)\b",
        r"\b(?:gtm|go.to.market|market segment|buyer persona)\b",
        r"\b(?:define|refine|update|review|assess) (?:my |our )?(?:strategy|icp|approach)\b",
    ],
    "contacts": [
        r"\b(?:contacts?|companies|companies?|leads?|prospects?)\b",
        r"\b(?:show me|find|list|filter|search|count|how many)\b",
        r"\b(?:enrichment|enrich|import|tag|segment)\b",
        r"\b(?:icp match|fit score|qualification)\b",
    ],
    "messages": [
        r"\b(?:message|outreach|email|write|draft|compose|generate)\b",
        r"\b(?:subject line|copy|tone|template|personalize)\b",
        r"\b(?:review|approve|reject|edit) (?:message|draft|outreach)\b",
    ],
    "campaign": [
        r"\b(?:campaign|send|launch|schedule|sequence|cadence)\b",
        r"\b(?:lemlist|outreach|follow.?up|touchpoint)\b",
        r"\b(?:open rate|reply rate|bounce|deliverability)\b",
    ],
    "documents": [
        r"\b(?:upload|pdf|document|file|image|screenshot)\b",
        r"\b(?:extract|analyze|read|parse|scan) (?:this |the )?(?:document|file|pdf|image)\b",
        r"\b(?:attached|attachment|here.?s a|look at this)\b",
    ],
}


def classify_intent(message: str) -> str:
    """Classify user message into a workflow phase intent.

    Uses keyword matching with scoring. Falls back to 'general' if ambiguous.

    Args:
        message: The user's message text.

    Returns:
        Intent string: 'strategy', 'contacts', 'messages', 'campaign',
        'documents', or 'general'.
    """
    if not message:
        return "general"

    message_lower = message.lower()
    scores = {}

    for intent, patterns in INTENT_KEYWORDS.items():
        score = 0
        for pattern in patterns:
            matches = re.findall(pattern, message_lower)
            score += len(matches)
        if score > 0:
            scores[intent] = score

    if not scores:
        return "general"

    # Get top intent
    top_intent = max(scores, key=scores.get)
    top_score = scores[top_intent]

    # Check for ambiguity: if second-best is close, fall back to general
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) > 1 and sorted_scores[1] >= top_score * 0.8:
        # Ambiguous - two intents score similarly
        return "general"

    # Require minimum confidence
    if top_score < 1:
        return "general"

    return top_intent


def get_tools_for_intent(
    intent: str, all_tool_names: Optional[list[str]] = None
) -> Optional[list[str]]:
    """Get the filtered tool names for a given intent.

    Args:
        intent: The classified intent string.
        all_tool_names: Full list of available tool names (for 'general' fallback).

    Returns:
        List of tool names to include, or None for 'general' (use all tools).
    """
    if intent == "general":
        return None  # Use all tools

    tool_subset = INTENT_TOOL_MAP.get(intent)
    if not tool_subset:
        return None

    # Filter to only tools that actually exist in the registry
    if all_tool_names:
        return [t for t in tool_subset if t in all_tool_names]

    return tool_subset


def filter_tools_by_message(message: str, all_tools: list[dict]) -> list[dict]:
    """Convenience function: classify intent and filter tool list.

    Args:
        message: User message text.
        all_tools: Full list of tool dicts (Claude API format).

    Returns:
        Filtered list of tool dicts for the detected intent.
    """
    intent = classify_intent(message)

    if intent == "general":
        return all_tools

    tool_names = INTENT_TOOL_MAP.get(intent)
    if not tool_names:
        return all_tools

    filtered = [t for t in all_tools if t.get("name") in tool_names]

    # Safety: if filtering removes too many tools, fall back to all
    if len(filtered) < 2:
        logger.debug(
            "Intent '%s' matched too few tools (%d), using all",
            intent,
            len(filtered),
        )
        return all_tools

    logger.debug(
        "Intent '%s': filtered %d -> %d tools",
        intent,
        len(all_tools),
        len(filtered),
    )
    return filtered

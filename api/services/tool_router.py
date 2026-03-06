"""Intent-aware tool routing for the AI agent (BL-264).

Filters the tool registry by playbook phase and page context so that
each agent call only receives relevant tools.  This reduces schema
tokens from ~2,500 to ~800-1,200 per call and improves tool selection
accuracy.
"""

from __future__ import annotations

from .tool_registry import get_tools_for_api

# Tools available in each playbook phase
PHASE_TOOLS: dict[str, list[str]] = {
    "strategy": [
        "get_strategy_document",
        "update_strategy_section",
        "append_to_section",
        "set_extracted_field",
        "track_assumption",
        "check_readiness",
        "set_icp_tiers",
        "set_buyer_personas",
    ],
    "contacts": [
        "get_strategy_document",
        "filter_contacts_by_icp",
        "get_enrichment_gaps",
        "trigger_enrichment",
        "analyze_contacts",
    ],
    "messages": [
        "get_strategy_document",
        "analyze_contacts",
    ],
    "campaign": [
        "get_strategy_document",
        "create_campaign",
        "assign_to_campaign",
    ],
}

# Tools always available regardless of phase
UNIVERSAL_TOOLS: list[str] = [
    "web_search",
    "research_company",
    "get_strategy_document",
]

# Extra tools available when the user is on a specific page
PAGE_CONTEXT_TOOLS: dict[str, list[str]] = {
    "contacts": [
        "filter_contacts_by_icp",
        "analyze_contacts",
        "get_enrichment_gaps",
    ],
    "companies": [
        "research_company",
        "analyze_contacts",
    ],
    "enrich": [
        "trigger_enrichment",
        "get_enrichment_gaps",
    ],
    "messages": [
        "analyze_contacts",
    ],
    "import": [],
}


def get_tools_for_context(phase: str, page_context: str | None = None) -> list[dict]:
    """Return tool definitions filtered by phase and page context.

    Args:
        phase: Current playbook phase (strategy, contacts, messages, campaign).
        page_context: Current page the user is viewing (optional override).

    Returns:
        List of tool dicts in Claude API format, filtered to relevant tools.
    """
    phase_names = set(PHASE_TOOLS.get(phase, []))
    universal_names = set(UNIVERSAL_TOOLS)
    allowed = phase_names | universal_names

    if page_context and page_context in PAGE_CONTEXT_TOOLS:
        allowed |= set(PAGE_CONTEXT_TOOLS[page_context])

    all_tools = get_tools_for_api()
    return [t for t in all_tools if t["name"] in allowed]

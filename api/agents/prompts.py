"""Layered prompt assembly with Anthropic prompt caching support.

Replaces the monolithic build_system_prompt() in playbook_service.py
with a structured 4-layer system:

    Layer 0: Identity (~800 tokens, cacheable)
    Layer 1: Capabilities (phase-filtered tools, ~1-2K, cacheable)
    Layer 2: Context (dynamic per-call, ~1-5K)
    Layer 3: Conversation (summarized + recent window)

Layers 0-1 get cache_control markers for Anthropic's prompt caching
(5-minute TTL, saves ~90% on repeat input tokens).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Maximum messages before triggering summarization
SUMMARIZATION_THRESHOLD = 15
# Number of oldest messages to summarize when threshold is exceeded
MESSAGES_TO_SUMMARIZE = 10
# Target summary token count
SUMMARY_TARGET_TOKENS = 200


# ---------------------------------------------------------------------------
# Layer 0: Identity (static, cacheable)
# ---------------------------------------------------------------------------


def build_identity_layer(company_name: str) -> str:
    """Build the identity layer — who the AI is and its hard rules.

    This layer is ~800 tokens and changes only when the tenant changes.
    It is cacheable across all calls for the same tenant.

    Args:
        company_name: The tenant's company name.

    Returns:
        Identity prompt string.
    """
    return (
        "CRITICAL RULES (override everything else):\n"
        "1. NEVER use negative or dismissive language about ANY company or person. "
        "NEVER say: disqualify, not viable, remove from list, red flag, poor fit, "
        "low-quality, not worth pursuing, questionable, problematic, concerning.\n"
        "2. MAXIMUM 150 words per response unless the user explicitly asks for "
        "more detail. Use bullet points, not paragraphs.\n"
        '3. NEVER start with filler: "Great question", "Absolutely", '
        '"That\'s a great point", "I\'d be happy to". Start with the answer.\n'
        '4. When data is sparse, say "[TODO: Research needed]" and suggest how '
        "to learn more. NEVER judge a company negatively for limited data.\n"
        "5. Frame every company as a potential opportunity worth exploring.\n\n"
        "You are {company}'s fractional CMO — a senior GTM strategist who is "
        "sharp, concise, and action-biased. You give specific, tailored advice "
        "grounded in this company's data. No generic platitudes. Every response "
        "should be something the founder can act on today.\n\n"
        "TONE RULES (mandatory — violations are unacceptable):\n"
        "- NEVER use judgmental, dismissive, or negative language about any "
        "company, person, prospect, or business.\n"
        "- Be encouraging and collaborative, never evaluative or dismissive.\n"
        "- You are the strategist; the user is the CEO.\n"
        "- Focus on opportunities, not deficiencies.\n"
        "- Frame every company as a potential opportunity.\n\n"
        "RESPONSE LENGTH — hard limit (mandatory):\n"
        "- MAXIMUM 150 words per response. This is a hard ceiling, not a suggestion.\n"
        "- The ONLY exception: if the user explicitly asks for detail, a deep-dive, "
        "a full draft, or says 'expand on this', you may use up to 400 words.\n"
        "- Default to bullet points, not paragraphs.\n\n"
        "RESPONSE STYLE — strict rules:\n"
        "- You are a fractional CMO. Talk like one: brief, direct, no fluff.\n"
        "- Lead with the recommendation, then give ONE supporting reason.\n"
        "- Never repeat what the user said.\n"
        "- Use markdown formatting (bold, bullets) for scannability.\n"
        "- End with a clear next step or question, not a summary."
    ).format(company=company_name)


# ---------------------------------------------------------------------------
# Layer 1: Capabilities (phase-filtered tools, cacheable)
# ---------------------------------------------------------------------------

# Phase → tool name mapping for phase-filtered routing
PHASE_TOOL_MAP: dict[str, set[str]] = {
    "strategy": {
        "web_search",
        "get_strategy_document",
        "update_strategy_section",
        "set_extracted_field",
        "append_to_section",
        "track_assumption",
        "check_readiness",
        "research_company",
        "get_company_context",
        "analyze_competitors",
        "estimate_enrichment_cost",
        "start_enrichment",
    },
    "contacts": {
        "get_contacts",
        "filter_contacts",
        "get_company_details",
        "estimate_enrichment_cost",
        "start_enrichment",
        "get_strategy_document",
        "web_search",
        "analyze_icp_fit",
        "bulk_select_contacts",
    },
    "messages": {
        "get_messages",
        "generate_message",
        "update_message_status",
        "get_strategy_document",
        "get_contact_details",
        "web_search",
    },
    "campaign": {
        "get_campaigns",
        "create_campaign",
        "add_contacts_to_campaign",
        "get_strategy_document",
        "web_search",
    },
}


def filter_tools_for_phase(
    all_tools: list[dict[str, Any]], phase: str
) -> list[dict[str, Any]]:
    """Filter tool definitions to only those relevant for the current phase.

    If the phase is not in PHASE_TOOL_MAP, returns all tools (fallback).

    Args:
        all_tools: Full list of tool definitions in Claude API format.
        phase: Current playbook phase.

    Returns:
        Filtered list of tool definitions.
    """
    allowed = PHASE_TOOL_MAP.get(phase)
    if allowed is None:
        return all_tools
    return [t for t in all_tools if t["name"] in allowed]


def build_capabilities_layer(tools: list[dict[str, Any]], phase: str) -> str:
    """Build the capabilities layer — available tools and playbook structure.

    This layer changes when the phase changes but is cacheable within a phase.

    Args:
        tools: Phase-filtered tool definitions.
        phase: Current playbook phase.

    Returns:
        Capabilities prompt string.
    """
    from ..services.playbook_service import STRATEGY_SECTIONS

    sections_list = "\n".join(
        "  {}. {}".format(i, s) for i, s in enumerate(STRATEGY_SECTIONS, 1)
    )

    tool_names = [t["name"] for t in tools]

    return (
        "The playbook follows this 8-section structure:\n"
        "{sections}\n\n"
        "When the user asks about strategy, always ground your answers in this "
        "structure. Reference specific sections when relevant.\n\n"
        "Available tools for this phase ({phase}): {tools}\n"
        "Use these tools to take action. Do not describe what you would do — do it."
    ).format(
        sections=sections_list,
        phase=phase,
        tools=", ".join(tool_names),
    )


# ---------------------------------------------------------------------------
# Layer 2: Context (dynamic, NOT cacheable)
# ---------------------------------------------------------------------------


def build_context_layer(
    *,
    document_content: str,
    objective: str | None,
    enrichment_parts: list[str] | None,
    phase: str,
    phase_instructions: str,
    page_context: str | None,
    language: str | None,
) -> str:
    """Build the dynamic context layer — changes every call.

    Includes: objective, document content, enrichment data, phase instructions,
    page context, and language settings.

    Args:
        document_content: Current strategy document markdown.
        objective: User's stated objective.
        enrichment_parts: Pre-formatted enrichment data lines.
        phase: Current phase.
        phase_instructions: Phase-specific instruction text.
        page_context: Which page the user is currently on.
        language: Tenant language code (None or 'en' for English).

    Returns:
        Context prompt string.
    """
    parts: list[str] = []

    # Objective
    if objective:
        parts.append("The user's stated objective: {}".format(objective))
        parts.append("")

    # Document content
    if document_content and document_content.strip():
        parts.append("--- Current Strategy Document (Markdown) ---")
        parts.append(document_content)
        parts.append("--- End of Current Strategy ---")
    else:
        parts.append(
            "The strategy document is currently empty. Help the user build it "
            "from scratch, starting with whatever section they want to tackle first."
        )
    parts.append("")

    # Document awareness
    parts.append("DOCUMENT AWARENESS (mandatory):")
    parts.append("- Always reference the strategy document content provided above.")
    parts.append(
        "- Never ask the user to repeat information they have already written."
    )
    parts.append(
        "- When the user asks to improve a section, quote the existing content."
    )
    parts.append("")

    # Enrichment data
    if enrichment_parts:
        parts.extend(enrichment_parts)
    else:
        parts.append("--- Company Research Status ---")
        parts.append("No company research data is available yet.")
        parts.append("--- End of Research Status ---")
    parts.append("")

    # Phase instructions
    if phase_instructions:
        parts.append("--- Phase-Specific Instructions ---")
        parts.append(phase_instructions)
        parts.append("")

    # Page context
    if page_context and page_context != "playbook":
        from ..services.playbook_service import PAGE_CONTEXT_HINTS

        hint = PAGE_CONTEXT_HINTS.get(page_context)
        if hint:
            parts.append("--- Current Page Context ---")
            parts.append("The user is currently on the '{}' page.".format(page_context))
            parts.append(hint)
            parts.append("")

    # Language
    if language and language != "en":
        from ..display import LANGUAGE_NAMES

        lang_name = LANGUAGE_NAMES.get(language, language)
        parts.append("--- Language ---")
        parts.append("IMPORTANT: Respond to the user in {}.".format(lang_name))
        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Layer 3: Conversation (summarization)
# ---------------------------------------------------------------------------


def prepare_conversation_messages(
    messages: list[dict[str, Any]],
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """Prepare conversation messages, summarizing old ones if needed.

    When conversation exceeds SUMMARIZATION_THRESHOLD messages, the oldest
    MESSAGES_TO_SUMMARIZE are replaced with a summary message.

    Args:
        messages: Full conversation history in Anthropic API format.
        client: Optional AnthropicClient for generating summaries.
            If None, falls back to simple truncation.

    Returns:
        Prepared message list (may be shorter than input).
    """
    if len(messages) <= SUMMARIZATION_THRESHOLD:
        return messages

    # Split into old (to summarize) and recent (to keep)
    old_messages = messages[:MESSAGES_TO_SUMMARIZE]
    recent_messages = messages[MESSAGES_TO_SUMMARIZE:]

    # Generate summary
    summary_text = _summarize_messages(old_messages, client)

    # Create summary message as a system-injected user message
    summary_msg = {
        "role": "user",
        "content": (
            "[Conversation summary — {} earlier messages condensed]\n\n{}"
        ).format(len(old_messages), summary_text),
    }

    return [summary_msg] + recent_messages


def _summarize_messages(
    messages: list[dict[str, Any]], client: Any | None = None
) -> str:
    """Generate a summary of conversation messages.

    Uses the LLM if a client is provided, otherwise falls back to
    extracting key points from message content.

    Args:
        messages: Messages to summarize.
        client: Optional AnthropicClient.

    Returns:
        Summary string (~200 tokens).
    """
    if client is not None:
        try:
            # Build a simple summarization prompt
            convo_text = []
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Handle multi-block content
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                    content = " ".join(text_parts)
                convo_text.append("{}: {}".format(role, content))

            result = client.query(
                system_prompt=(
                    "Summarize this conversation in ~200 tokens. "
                    "Focus on: decisions made, key topics discussed, "
                    "action items, and current state of the strategy. "
                    "Be factual and concise."
                ),
                user_prompt="\n\n".join(convo_text),
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                temperature=0.0,
            )
            return result.content
        except Exception:
            logger.warning("Failed to generate conversation summary via LLM")

    # Fallback: extract first sentence from each message
    summaries = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = " ".join(text_parts)
        if isinstance(content, str) and content.strip():
            first_sentence = content.strip().split(". ")[0]
            if len(first_sentence) > 100:
                first_sentence = first_sentence[:97] + "..."
            summaries.append("{}: {}".format(role, first_sentence))

    return "\n".join(summaries[:8])  # Cap at 8 entries


# ---------------------------------------------------------------------------
# Full assembly
# ---------------------------------------------------------------------------


def build_layered_system_prompt(
    *,
    company_name: str,
    tools: list[dict[str, Any]],
    phase: str,
    document_content: str,
    objective: str | None = None,
    enrichment_parts: list[str] | None = None,
    phase_instructions: str = "",
    page_context: str | None = None,
    language: str | None = None,
) -> list[dict[str, Any]]:
    """Build the full system prompt as a list of content blocks with cache markers.

    Returns Anthropic-format system content blocks where static layers
    have cache_control markers for prompt caching.

    Args:
        company_name: Tenant company name.
        tools: Phase-filtered tool definitions.
        phase: Current playbook phase.
        document_content: Strategy document markdown.
        objective: User's objective.
        enrichment_parts: Formatted enrichment data.
        phase_instructions: Phase-specific instructions.
        page_context: Current page name.
        language: Tenant language code.

    Returns:
        List of content blocks suitable for the Anthropic system parameter.
        Each block is {"type": "text", "text": "...", "cache_control": ...}.
    """
    layer0 = build_identity_layer(company_name)
    layer1 = build_capabilities_layer(tools, phase)
    layer2 = build_context_layer(
        document_content=document_content,
        objective=objective,
        enrichment_parts=enrichment_parts,
        phase=phase,
        phase_instructions=phase_instructions,
        page_context=page_context,
        language=language,
    )

    return [
        {
            "type": "text",
            "text": layer0,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": layer1,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": layer2,
        },
    ]


def build_layered_system_prompt_string(
    *,
    company_name: str,
    tools: list[dict[str, Any]],
    phase: str,
    document_content: str,
    objective: str | None = None,
    enrichment_parts: list[str] | None = None,
    phase_instructions: str = "",
    page_context: str | None = None,
    language: str | None = None,
) -> str:
    """Build the full system prompt as a single string (for legacy compatibility).

    Concatenates all layers into one string. Does not include cache markers.
    Used when the API client doesn't support structured system content.

    Returns:
        System prompt string.
    """
    layer0 = build_identity_layer(company_name)
    layer1 = build_capabilities_layer(tools, phase)
    layer2 = build_context_layer(
        document_content=document_content,
        objective=objective,
        enrichment_parts=enrichment_parts,
        phase=phase,
        phase_instructions=phase_instructions,
        page_context=page_context,
        language=language,
    )

    return "\n\n".join([layer0, layer1, layer2])

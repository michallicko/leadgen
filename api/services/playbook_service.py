"""Playbook service: system prompt construction and message formatting for AI chat.

Builds the system prompt that positions the AI as a GTM strategy consultant,
and converts DB chat history into Anthropic API message format.
"""

import json
import logging

logger = logging.getLogger(__name__)

# Maximum number of historical messages to include in context
MAX_HISTORY_MESSAGES = 20

STRATEGY_SECTIONS = [
    "Executive Summary",
    "ICP (Ideal Customer Profile)",
    "Buyer Personas",
    "Value Proposition",
    "Competitive Positioning",
    "Channel Strategy",
    "Messaging Framework",
    "Success Metrics",
]


def build_system_prompt(tenant, document, enrichment_data=None):
    """Build the system prompt for the playbook AI assistant.

    Positions the AI as a GTM strategy consultant with context about the
    tenant's company, their current strategy document, and any enrichment data.

    Args:
        tenant: Tenant model instance (has .name, .slug).
        document: StrategyDocument model instance (has .content dict).
        enrichment_data: Optional dict of company enrichment data (industry,
            company_intel, etc.) to include as research context.

    Returns:
        str: System prompt string for the Anthropic API.
    """
    sections_list = "\n".join(
        "  {}. {}".format(i, s) for i, s in enumerate(STRATEGY_SECTIONS, 1)
    )

    parts = [
        "You are a senior GTM (go-to-market) strategy consultant helping {company} "
        "build and refine their GTM playbook. You are practical, specific, and "
        "action-oriented. Avoid generic advice \u2014 tailor everything to this company's "
        "context and data.".format(company=tenant.name),
        "",
        "The playbook follows this 8-section structure:",
        sections_list,
        "",
        "When the user asks about strategy, always ground your answers in this "
        "structure. Reference specific sections when relevant. If the user asks "
        "you to draft or revise a section, produce clear, concise content that "
        "can be directly pasted into the playbook.",
    ]

    # Include existing strategy document content as context
    content = document.content if document.content else {}
    if content:
        content_str = json.dumps(content, indent=2, default=str)
        parts.extend([
            "",
            "--- Current Strategy Document ---",
            content_str,
            "--- End of Current Strategy ---",
        ])
    else:
        parts.extend([
            "",
            "The strategy document is currently empty. Help the user build it "
            "from scratch, starting with whatever section they want to tackle first.",
        ])

    # Include enrichment/research data if available
    if enrichment_data:
        enrichment_str = json.dumps(enrichment_data, indent=2, default=str)
        parts.extend([
            "",
            "--- Company Research Data ---",
            enrichment_str,
            "--- End of Research Data ---",
            "",
            "Use this research data to ground your recommendations. Reference "
            "specific findings when making suggestions.",
        ])

    parts.extend([
        "",
        "Keep responses focused and actionable. Use bullet points and headers "
        "for readability. When suggesting changes to the playbook, be specific "
        "about which section and what content to add or modify.",
    ])

    return "\n".join(parts)


EXTRACTION_SCHEMA = """\
{
  "icp": {
    "industries": ["string"],
    "company_size": {"min": 0, "max": 0},
    "geographies": ["string"],
    "tech_signals": ["string"],
    "triggers": ["string"],
    "disqualifiers": ["string"]
  },
  "personas": [
    {
      "title_patterns": ["string"],
      "pain_points": ["string"],
      "goals": ["string"]
    }
  ],
  "messaging": {
    "tone": "string",
    "themes": ["string"],
    "angles": ["string"],
    "proof_points": ["string"]
  },
  "channels": {
    "primary": "string",
    "secondary": ["string"],
    "cadence": "string"
  },
  "metrics": {
    "reply_rate_target": 0.0,
    "meeting_rate_target": 0.0,
    "pipeline_goal_eur": 0,
    "timeline_months": 0
  }
}"""


def build_extraction_prompt(document_content):
    """Build the system + user prompt pair for structured data extraction.

    Instructs the LLM to extract ICP, personas, messaging, channels, and
    metrics from a GTM strategy document into a fixed JSON schema.

    Args:
        document_content: The strategy document's ``content`` dict (rich doc).

    Returns:
        tuple[str, str]: (system_prompt, user_message) ready for
        ``AnthropicClient.query()``.
    """
    system_prompt = (
        "You are a data extraction assistant. Your task is to extract "
        "structured data from a GTM (go-to-market) strategy document.\n\n"
        "Output ONLY valid JSON matching this exact schema. No markdown "
        "fences, no explanation, no commentary -- just the JSON object.\n\n"
        "If a field cannot be determined from the document, use empty "
        "arrays for list fields, empty strings for string fields, and "
        "zero for numeric fields.\n\n"
        "Required JSON schema:\n" + EXTRACTION_SCHEMA
    )

    content_str = json.dumps(document_content, indent=2, default=str)
    user_message = (
        "Extract structured data from this GTM strategy document:\n\n"
        + content_str
    )

    return system_prompt, user_message


def build_messages(chat_history, user_message):
    """Convert DB chat history into Anthropic API message format.

    Takes a list of StrategyChatMessage model objects and a new user message
    string, formats them as Anthropic-compatible message dicts, and caps the
    history to the last MAX_HISTORY_MESSAGES entries.

    Args:
        chat_history: List of StrategyChatMessage objects (must have .role
            and .content attributes).
        user_message: The new user message text to append.

    Returns:
        list[dict]: Messages in Anthropic format:
            [{"role": "user"|"assistant", "content": "text"}, ...]
    """
    # Limit history to last N messages
    recent = chat_history[-MAX_HISTORY_MESSAGES:] if len(chat_history) > MAX_HISTORY_MESSAGES else chat_history

    messages = [
        {"role": msg.role, "content": msg.content}
        for msg in recent
    ]

    # Append the new user message
    messages.append({"role": "user", "content": user_message})

    return messages

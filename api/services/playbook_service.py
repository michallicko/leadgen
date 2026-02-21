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
        document: StrategyDocument model instance (has .content str/dict,
            .objective str).
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
        "you to draft or revise a section, produce clear, concise markdown content "
        "that can be directly pasted into the playbook.",
    ]

    # Include the user's stated objective
    objective = getattr(document, "objective", None)
    if objective:
        parts.extend(
            [
                "",
                "The user's stated objective: {}".format(objective),
            ]
        )

    # Include existing strategy document content as context
    content = document.content if document.content else ""
    if isinstance(content, dict):
        # Legacy JSONB content — serialize for prompt
        content = json.dumps(content, indent=2, default=str)
    if content and content.strip():
        parts.extend(
            [
                "",
                "--- Current Strategy Document (Markdown) ---",
                content,
                "--- End of Current Strategy ---",
            ]
        )
    else:
        parts.extend(
            [
                "",
                "The strategy document is currently empty. Help the user build it "
                "from scratch, starting with whatever section they want to tackle first.",
            ]
        )

    # Include enrichment/research data if available
    if enrichment_data:
        enrichment_str = json.dumps(enrichment_data, indent=2, default=str)
        parts.extend(
            [
                "",
                "--- Company Research Data ---",
                enrichment_str,
                "--- End of Research Data ---",
                "",
                "Use this research data to ground your recommendations. Reference "
                "specific findings when making suggestions.",
            ]
        )

    parts.extend(
        [
            "",
            "Keep responses focused and actionable. Use markdown formatting "
            "(headers, bullet points, bold) for readability. When suggesting "
            "changes to the playbook, be specific about which section and what "
            "content to add or modify.",
        ]
    )

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
        document_content: The strategy document's ``content`` (markdown string
            or legacy dict).

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

    if isinstance(document_content, dict):
        content_str = json.dumps(document_content, indent=2, default=str)
    else:
        content_str = str(document_content) if document_content else ""
    user_message = (
        "Extract structured data from this GTM strategy document:\n\n" + content_str
    )

    return system_prompt, user_message


def build_seeded_template(objective=None, enrichment_data=None):
    """Generate a markdown template for a new strategy document.

    Args:
        objective: Optional user-stated objective to embed in the summary.
        enrichment_data: Optional dict from _load_enrichment_data with
            company profile, signals, and market data.

    Returns:
        str: Markdown string with 8 sections pre-populated with guidance.
    """
    # Extract useful fields from enrichment data if available
    company_name = ""
    industry = ""
    description = ""
    company_intel = ""
    key_products = ""
    customer_segments = ""
    competitors = ""
    if enrichment_data:
        # Company-level data (from Company model fields)
        co = enrichment_data.get("company") or {}
        company_name = co.get("name") or ""
        industry = co.get("industry") or ""
        description = co.get("summary") or ""
        # Profile enrichment data (flat keys from CompanyEnrichmentProfile)
        company_intel = enrichment_data.get("company_intel") or ""
        key_products = enrichment_data.get("key_products") or ""
        customer_segments = enrichment_data.get("customer_segments") or ""
        competitors = enrichment_data.get("competitors") or ""
        if not description and company_intel:
            description = company_intel

    header = "{} \u2014 GTM Strategy".format(company_name) if company_name else "GTM Strategy"

    summary_parts = ["**Objective:** {}".format(objective or "Define your go-to-market objective")]
    if company_name:
        summary_parts.append("**Company:** {}".format(company_name))
    if industry:
        summary_parts.append("**Industry:** {}".format(industry))
    if description:
        summary_parts.append(description)
    summary = "\n\n".join(summary_parts)

    icp_hint = "Define your target customer segments based on industry, company size, and buying signals."
    if customer_segments:
        icp_hint += "\n\n**Known Segments:** " + customer_segments

    value_hint = "Articulate your core value proposition and key messaging themes."
    if key_products:
        value_hint += "\n\n**Key Products/Services:** " + key_products

    competitive_hint = "Map your competitive landscape and differentiation."
    if competitors:
        competitive_hint += "\n\n**Known Competitors:** " + competitors

    return """# {header}

## Executive Summary

{summary}

## Ideal Customer Profile (ICP)

{icp_hint}

## Buyer Personas

Identify 2-3 key buyer personas with their titles, pain points, and goals.

## Value Proposition & Messaging

{value_hint}

## Competitive Positioning

{competitive_hint}

## Channel Strategy

Outline your primary and secondary outreach channels, cadence, and sequencing.

## Messaging Framework

Define core messaging pillars aligned with your value proposition and personas.

## Metrics & KPIs

Set measurable targets: reply rates, meeting rates, pipeline goals, and timeline.

## 90-Day Action Plan

Break your strategy into concrete weekly/monthly milestones for the first 90 days.
""".format(
        header=header,
        summary=summary,
        icp_hint=icp_hint,
        value_hint=value_hint,
        competitive_hint=competitive_hint,
    ).strip()


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
    recent = (
        chat_history[-MAX_HISTORY_MESSAGES:]
        if len(chat_history) > MAX_HISTORY_MESSAGES
        else chat_history
    )

    messages = [{"role": msg.role, "content": msg.content} for msg in recent]

    # Append the new user message
    messages.append({"role": "user", "content": user_message})

    return messages

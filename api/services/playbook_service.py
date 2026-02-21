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


def _format_enrichment_for_prompt(enrichment_data):
    """Format enrichment data as structured sections for the system prompt.

    Instead of dumping raw JSON, organizes the research data into labeled
    sections so the AI can reference specific findings by category.
    """
    parts = ["", "--- Company Research Data ---", ""]
    co = enrichment_data.get("company") or {}

    # Company profile
    profile_fields = [
        ("Name", co.get("name")),
        ("Industry", co.get("industry")),
        ("Category", co.get("industry_category")),
        ("Size", co.get("company_size")),
        ("Revenue", co.get("revenue_range")),
        (
            "HQ",
            "{}, {}".format(co.get("hq_city", ""), co.get("hq_country", ""))
            if co.get("hq_city")
            else co.get("hq_country"),
        ),
    ]
    profile_lines = ["  {}: {}".format(k, v) for k, v in profile_fields if v]
    if profile_lines:
        parts.append("COMPANY PROFILE:")
        parts.extend(profile_lines)
        parts.append("")

    # Company overview & intel
    overview = enrichment_data.get("company_overview") or ""
    intel = enrichment_data.get("company_intel") or ""
    if overview or intel:
        parts.append("COMPANY OVERVIEW:")
        if overview:
            parts.append("  " + overview)
        if intel and intel != overview:
            parts.append("  " + intel)
        parts.append("")

    # Products & tech
    products = enrichment_data.get("key_products") or ""
    tech = enrichment_data.get("tech_stack") or ""
    if products or tech:
        parts.append("PRODUCTS & TECHNOLOGY:")
        if products:
            parts.append("  Products: " + products)
        if tech:
            parts.append("  Tech Stack: " + tech)
        parts.append("")

    # Market & competition
    competitors = enrichment_data.get("competitors") or ""
    segments = enrichment_data.get("customer_segments") or ""
    if competitors or segments:
        parts.append("MARKET & COMPETITION:")
        if segments:
            parts.append("  Customer Segments: " + segments)
        if competitors:
            parts.append("  Competitors: " + competitors)
        parts.append("")

    # Pain points & opportunities (L2)
    pain = enrichment_data.get("pain_hypothesis") or ""
    opps = enrichment_data.get("ai_opportunities") or ""
    wins = enrichment_data.get("quick_wins") or ""
    if pain or opps or wins:
        parts.append("PAIN POINTS & OPPORTUNITIES:")
        if pain:
            parts.append("  Pain Hypothesis: " + pain)
        if opps:
            parts.append("  AI Opportunities: " + opps)
        if wins:
            parts.append("  Quick Wins: " + wins)
        parts.append("")

    # Signals
    digital = enrichment_data.get("digital_initiatives") or ""
    hiring = enrichment_data.get("hiring_signals") or ""
    ai_level = enrichment_data.get("ai_adoption_level") or ""
    growth = enrichment_data.get("growth_indicators") or ""
    if digital or hiring or ai_level or growth:
        parts.append("MARKET SIGNALS:")
        if digital:
            parts.append("  Digital Initiatives: " + digital)
        if hiring:
            parts.append("  Hiring Signals: " + hiring)
        if ai_level:
            parts.append("  AI Adoption: " + ai_level)
        if growth:
            parts.append("  Growth Indicators: " + growth)
        parts.append("")

    # Leadership & certs
    leaders = enrichment_data.get("leadership_team") or ""
    certs = enrichment_data.get("certifications") or ""
    if leaders or certs:
        parts.append("LEADERSHIP & COMPLIANCE:")
        if leaders:
            parts.append("  Leadership: " + leaders)
        if certs:
            parts.append("  Certifications: " + certs)
        parts.append("")

    # Market events
    news = enrichment_data.get("recent_news") or ""
    funding = enrichment_data.get("funding_history") or ""
    if news or funding:
        parts.append("RECENT EVENTS:")
        if news:
            parts.append("  News: " + news)
        if funding:
            parts.append("  Funding: " + funding)
        parts.append("")

    # L1 triage
    triage = enrichment_data.get("triage_notes") or ""
    score = enrichment_data.get("pre_score")
    if triage or score:
        parts.append("QUALIFICATION:")
        if triage:
            parts.append("  Triage Notes: " + triage)
        if score is not None:
            parts.append("  Pre-Score: {}/100".format(score))
        parts.append("")

    parts.append("--- End of Research Data ---")
    parts.append("")
    parts.append(
        "Use this research data to ground your recommendations. Reference "
        "specific findings from the sections above when making suggestions."
    )

    return parts


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

    # Include enrichment/research data as structured sections
    if enrichment_data:
        parts.extend(_format_enrichment_for_prompt(enrichment_data))

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


def _get(data, key, default=""):
    """Safely extract a string value from a dict, returning default if missing."""
    val = data.get(key) or default
    if isinstance(val, list):
        return "\n".join(f"- {item}" for item in val)
    if isinstance(val, dict):
        import json

        return json.dumps(val, indent=2)
    return str(val) if val else default


def build_seeded_template(objective=None, enrichment_data=None):
    """Generate a markdown template for a new strategy document.

    Args:
        objective: Optional user-stated objective to embed in the summary.
        enrichment_data: Optional dict from _load_enrichment_data with
            company profile, signals, and market data.

    Returns:
        str: Markdown string with 9 sections pre-populated with company-
        specific content from enrichment data.
    """
    if not enrichment_data:
        return _build_empty_template(objective)

    co = enrichment_data.get("company") or {}
    company_name = _get(co, "name")
    industry = _get(co, "industry")
    industry_category = _get(co, "industry_category")
    summary = _get(co, "summary")
    company_size = _get(co, "company_size")
    revenue_range = _get(co, "revenue_range")
    hq_city = _get(co, "hq_city")
    hq_country = _get(co, "hq_country")

    # Profile fields
    company_intel = _get(enrichment_data, "company_intel")
    key_products = _get(enrichment_data, "key_products")
    customer_segments = _get(enrichment_data, "customer_segments")
    competitors = _get(enrichment_data, "competitors")
    tech_stack = _get(enrichment_data, "tech_stack")
    leadership_team = _get(enrichment_data, "leadership_team")
    certifications = _get(enrichment_data, "certifications")

    # L1 fields
    triage_notes = _get(enrichment_data, "triage_notes")

    # L2 fields
    company_overview = _get(enrichment_data, "company_overview")
    ai_opportunities = _get(enrichment_data, "ai_opportunities")
    pain_hypothesis = _get(enrichment_data, "pain_hypothesis")
    quick_wins = _get(enrichment_data, "quick_wins")

    # Signals fields
    digital_initiatives = _get(enrichment_data, "digital_initiatives")
    hiring_signals = _get(enrichment_data, "hiring_signals")
    ai_adoption_level = _get(enrichment_data, "ai_adoption_level")
    growth_indicators = _get(enrichment_data, "growth_indicators")

    # Market fields
    recent_news = _get(enrichment_data, "recent_news")
    funding_history = _get(enrichment_data, "funding_history")

    header = (
        "{} \u2014 GTM Strategy".format(company_name)
        if company_name
        else "GTM Strategy"
    )

    # --- Executive Summary ---
    exec_parts = []
    exec_parts.append(
        "**Objective:** {}".format(objective or "Define your go-to-market objective")
    )
    if company_name:
        exec_parts.append("**Company:** {}".format(company_name))
    if industry:
        line = "**Industry:** {}".format(industry)
        if industry_category:
            line += " ({})".format(industry_category)
        exec_parts.append(line)
    if company_size:
        line = "**Size:** {} employees".format(company_size)
        if revenue_range:
            line += " | **Revenue:** {}".format(revenue_range)
        exec_parts.append(line)
    if hq_city and hq_country:
        exec_parts.append("**HQ:** {}, {}".format(hq_city, hq_country))
    description = summary or company_intel or ""
    if description:
        exec_parts.append("")
        exec_parts.append(description)
    if company_overview and company_overview != description:
        exec_parts.append("")
        exec_parts.append(company_overview)
    if recent_news:
        exec_parts.append("")
        exec_parts.append("**Recent Developments:** {}".format(recent_news))
    if funding_history:
        exec_parts.append("")
        exec_parts.append("**Funding:** {}".format(funding_history))
    exec_summary = "\n".join(exec_parts)

    # --- ICP ---
    icp_parts = []
    if customer_segments:
        icp_parts.append("**Target Segments:** {}".format(customer_segments))
    if company_size:
        icp_parts.append(
            "**Company Profile:** {} employees, {} revenue".format(
                company_size, revenue_range or "undisclosed"
            )
        )
    if triage_notes:
        icp_parts.append("")
        icp_parts.append("**Triage Notes:** {}".format(triage_notes))
    if growth_indicators:
        icp_parts.append("")
        icp_parts.append("**Growth Signals to Target:** {}".format(growth_indicators))
    if hiring_signals:
        icp_parts.append("")
        icp_parts.append("**Hiring Signals:** {}".format(hiring_signals))
    if not icp_parts:
        icp_parts.append(
            "Define your target customer segments based on industry, "
            "company size, and buying signals."
        )
    icp_content = "\n".join(icp_parts)

    # --- Buyer Personas ---
    persona_parts = []
    if leadership_team:
        persona_parts.append("**Key Decision-Makers:** {}".format(leadership_team))
        persona_parts.append("")
    if triage_notes:
        persona_parts.append("**Buying Dynamics:** {}".format(triage_notes))
        persona_parts.append("")
    if ai_adoption_level:
        persona_parts.append("**AI Adoption Level:** {}".format(ai_adoption_level))
        persona_parts.append("")
    if leadership_team or triage_notes:
        persona_parts.append(
            "Based on the leadership and buying dynamics above, build 2-3 "
            "buyer persona profiles. For each, specify the title pattern, "
            "key pain points, and primary goals."
        )
    else:
        persona_parts.append(
            "Build 2-3 buyer persona profiles with title patterns, "
            "pain points, and goals."
        )
    persona_content = "\n".join(persona_parts)

    # --- Value Proposition ---
    value_parts = []
    if key_products:
        value_parts.append("**Products/Services:** {}".format(key_products))
    if pain_hypothesis:
        value_parts.append("")
        value_parts.append("**Pain Points Identified:**")
        value_parts.append("")
        value_parts.append(pain_hypothesis)
    if ai_opportunities:
        value_parts.append("")
        value_parts.append("**AI/Tech Opportunities:**")
        value_parts.append("")
        value_parts.append(ai_opportunities)
    if not value_parts:
        value_parts.append(
            "Articulate your core value proposition and key messaging themes."
        )
    value_content = "\n".join(value_parts)

    # --- Competitive Positioning ---
    comp_parts = []
    if competitors:
        comp_parts.append("**Competitive Landscape:** {}".format(competitors))
    if tech_stack:
        comp_parts.append("")
        comp_parts.append("**Tech Stack:** {}".format(tech_stack))
    if certifications:
        comp_parts.append("")
        comp_parts.append("**Certifications:** {}".format(certifications))
    if digital_initiatives:
        comp_parts.append("")
        comp_parts.append("**Digital Initiatives:** {}".format(digital_initiatives))
    if not comp_parts:
        comp_parts.append("Map your competitive landscape and differentiation.")
    comp_content = "\n".join(comp_parts)

    # --- Channel Strategy ---
    channel_parts = []
    if customer_segments:
        channel_parts.append("**Target Audience:** {}".format(customer_segments))
        channel_parts.append("")
    if hiring_signals:
        channel_parts.append("**Leverage Hiring Signals:** {}".format(hiring_signals))
        channel_parts.append("")
    channel_parts.append(
        "Prioritize channels based on where these buyer personas engage. "
        "Consider LinkedIn for B2B outreach, industry events, "
        "and partnerships for warm introductions."
    )
    channel_content = "\n".join(channel_parts)

    # --- Messaging Framework ---
    msg_parts = []
    if pain_hypothesis:
        msg_parts.append("**Lead with Pain Points:**")
        msg_parts.append("")
        msg_parts.append(pain_hypothesis)
        msg_parts.append("")
    if ai_opportunities:
        msg_parts.append("**Offer AI-Powered Solutions:**")
        msg_parts.append("")
        msg_parts.append(ai_opportunities)
        msg_parts.append("")
    msg_parts.append(
        "Build messaging pillars that connect the identified pain points "
        "to your solution, using proof points and case studies relevant "
        "to the {} industry.".format(industry or "target")
    )
    msg_content = "\n".join(msg_parts)

    # --- Metrics ---
    metrics_parts = []
    if growth_indicators:
        metrics_parts.append("**Company Growth Context:** {}".format(growth_indicators))
        metrics_parts.append("")
    metrics_parts.append("Target metrics aligned with the company's growth trajectory:")
    metrics_parts.append("")
    metrics_parts.append("- **Reply rate target:** __%")
    metrics_parts.append("- **Meeting rate target:** __%")
    metrics_parts.append("- **Pipeline goal:** $__")
    metrics_parts.append("- **Timeline:** __ months")
    metrics_content = "\n".join(metrics_parts)

    # --- 90-Day Action Plan ---
    action_parts = []
    if quick_wins:
        action_parts.append("**Quick Wins (First 30 Days):**")
        action_parts.append("")
        action_parts.append(quick_wins)
        action_parts.append("")
    action_parts.append("**Days 31-60:** Build on quick wins, expand outreach")
    action_parts.append("")
    action_parts.append("**Days 61-90:** Optimize based on metrics, scale what works")
    action_content = "\n".join(action_parts)

    return """# {header}

## Executive Summary

{exec_summary}

## Ideal Customer Profile (ICP)

{icp_content}

## Buyer Personas

{persona_content}

## Value Proposition & Messaging

{value_content}

## Competitive Positioning

{comp_content}

## Channel Strategy

{channel_content}

## Messaging Framework

{msg_content}

## Metrics & KPIs

{metrics_content}

## 90-Day Action Plan

{action_content}""".format(
        header=header,
        exec_summary=exec_summary,
        icp_content=icp_content,
        persona_content=persona_content,
        value_content=value_content,
        comp_content=comp_content,
        channel_content=channel_content,
        msg_content=msg_content,
        metrics_content=metrics_content,
        action_content=action_content,
    ).strip()


def _build_empty_template(objective=None):
    """Minimal template when no enrichment data is available."""
    return """# GTM Strategy

## Executive Summary

**Objective:** {objective}

## Ideal Customer Profile (ICP)

Define your target customer segments based on industry, company size, and buying signals.

## Buyer Personas

Identify 2-3 key buyer personas with their titles, pain points, and goals.

## Value Proposition & Messaging

Articulate your core value proposition and key messaging themes.

## Competitive Positioning

Map your competitive landscape and differentiation.

## Channel Strategy

Outline your primary and secondary outreach channels, cadence, and sequencing.

## Messaging Framework

Define core messaging pillars aligned with your value proposition and personas.

## Metrics & KPIs

Set measurable targets: reply rates, meeting rates, pipeline goals, and timeline.

## 90-Day Action Plan

Break your strategy into concrete weekly/monthly milestones for the first 90 days.""".format(
        objective=objective or "Define your go-to-market objective",
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

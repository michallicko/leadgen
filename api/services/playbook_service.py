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


PHASE_INSTRUCTIONS = {
    "strategy": (
        "You are in the STRATEGY phase. Focus on helping the user define their "
        "GTM strategy: ICP, buyer personas, value proposition, competitive "
        "positioning, channel strategy, messaging framework, and success metrics.\n\n"
        "When the strategy feels specific enough (ICP has concrete disqualifiers, "
        "personas have real title patterns, metrics have numbers), suggest moving "
        'to the Contacts phase by saying: "Your strategy looks ready. Want to '
        'move to the Contacts phase to select your target contacts?"'
    ),
    "contacts": (
        "You are in the CONTACTS phase. The user's ICP and personas have been "
        "defined. Help them select and filter contacts that match their strategy.\n\n"
        "Guide the user to:\n"
        "- Review the pre-applied ICP filters\n"
        "- Adjust filters based on their priorities\n"
        "- Select specific contacts for outreach\n"
        "- Consider contact quality and engagement signals\n\n"
        "When contacts are selected, suggest moving to Messages phase."
    ),
    "messages": (
        "You are in the MESSAGES phase. The user has selected contacts and now "
        "needs to generate and review personalized outreach messages.\n\n"
        "Help the user:\n"
        "- Review generated messages for quality and personalization\n"
        "- Adjust tone, length, and angle based on their preferences\n"
        "- Approve or regenerate individual messages\n"
        "- Ensure messaging aligns with the strategy's messaging framework\n\n"
        "When messages are reviewed, suggest launching the campaign."
    ),
    "campaign": (
        "You are in the CAMPAIGN phase. Messages have been reviewed and the user "
        "is ready to launch their outreach campaign.\n\n"
        "Help the user:\n"
        "- Configure campaign settings (channels, cadence, timing)\n"
        "- Review the final contact list and message assignments\n"
        "- Set expectations for response rates and follow-up\n"
        "- Launch the campaign or schedule it for later"
    ),
}


def build_system_prompt(tenant, document, enrichment_data=None, phase=None):
    """Build the system prompt for the playbook AI assistant.

    Positions the AI as a GTM strategy consultant with context about the
    tenant's company, their current strategy document, and any enrichment data.
    Appends phase-specific instructions when phase is given.

    Args:
        tenant: Tenant model instance (has .name, .slug).
        document: StrategyDocument model instance (has .content str/dict,
            .objective str).
        enrichment_data: Optional dict of company enrichment data (industry,
            company_intel, etc.) to include as research context.
        phase: Optional phase string to override document's phase for prompt
            construction. Does not change the stored phase.

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

    # Instruct the AI to treat the document as the single source of truth
    parts.extend(
        [
            "",
            "DOCUMENT AWARENESS (mandatory):",
            "- Always reference the strategy document content provided above. "
            "The user is editing this document in a side-by-side editor and "
            "expects you to know everything already written in it.",
            "- Never ask the user to repeat information they have already "
            "written in the document. If they defined their ICP, personas, "
            "or value proposition in the document, reference it directly.",
            "- When the user asks to improve or revise a section, quote or "
            "reference the existing content before suggesting changes.",
            "- If the document is empty, proactively guide the user to start "
            "filling in sections rather than asking what they want to do.",
        ]
    )

    # Include enrichment/research data as structured sections
    if enrichment_data:
        parts.extend(_format_enrichment_for_prompt(enrichment_data))

    parts.extend(
        [
            "",
            "TONE RULES (mandatory):",
            "- NEVER use judgmental or dismissive language about any company, "
            "person, or business. Forbidden phrases include: "
            '"DISQUALIFY", "no verifiable business presence", '
            '"minimal digital footprint", "insufficient data", '
            '"poor online presence", "no evidence of".',
            "- When research data is limited or missing, reframe constructively: "
            "\"I found limited information online — let's fill in the details "
            'together" or "This section needs your input to be accurate."',
            "- Be encouraging and collaborative, never evaluative or dismissive.",
            "- You are the strategist; the user is the CEO. A strategist never "
            "insults their client's business or prospects.",
            "- Focus on opportunities, not deficiencies. Instead of "
            '"They lack X", say "There\'s an opportunity to strengthen X."',
            "",
            "HANDLING SPARSE DATA:",
            "- When research data is thin for any strategy section, insert a "
            "visible TODO marker: **TODO**: [description of what is needed]",
            "- Always include a concrete example after the TODO so the user has "
            "a starting point, not a blank wall.",
            '- Example: "**TODO**: Define your primary ICP\\n\\n'
            "*Example: Mid-market SaaS companies (50-500 employees) in DACH "
            "region struggling with manual lead qualification, typically with "
            '2-5 person sales teams*"',
            "- Never leave a section completely empty. Either populate it from "
            "research data or provide a TODO with an example.",
            "",
            "RESPONSE STYLE RULES:",
            "- Be concise: 2-4 sentences by default. Only go longer when the "
            "user explicitly asks for detail or the content genuinely requires it.",
            "- Use bullet points over long paragraphs.",
            "- Lead with the insight or recommendation, not the reasoning.",
            "- Never pad with filler phrases like 'Great question!', "
            "'That's a really interesting point', or 'Absolutely!'.",
            "- When presenting options, use a compact format: bullets with "
            "1-line descriptions.",
            "- Use markdown formatting (headers, bullet points, bold, code "
            "blocks) for readability.",
            "- When suggesting changes to the playbook, be specific about "
            "which section and what content to add or modify.",
        ]
    )

    # Append phase-specific instructions
    active_phase = phase or getattr(document, "phase", "strategy") or "strategy"
    phase_text = PHASE_INSTRUCTIONS.get(active_phase, "")
    if phase_text:
        parts.extend(["", "--- Phase-Specific Instructions ---", phase_text])

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
    """Safely extract a value from a dict, returning default if missing."""
    val = data.get(key) or default
    return val if val else default


def _clean_industry(raw):
    """Convert snake_case industry names to title case.

    E.g. 'financial_services' -> 'Financial Services', 'technology' -> 'Technology'.
    Leaves already-formatted names unchanged.
    """
    if not raw:
        return ""
    return raw.replace("_", " ").title() if "_" in raw else raw


def _parse_structured(val):
    """Parse a value that might be a JSON string, list, dict, or plain string.

    Returns the parsed Python object (list/dict) or the original string.
    """
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        stripped = val.strip()
        if stripped.startswith(("[", "{")):
            try:
                return json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                pass
    return val


def _format_opportunities(raw):
    """Format ai_opportunities into structured markdown subsections.

    Handles: JSON string, list of dicts, list of strings, or plain string.
    Each opportunity gets a heading with priority/timeline badges.
    """
    parsed = _parse_structured(raw)
    if not parsed:
        return ""

    if isinstance(parsed, str):
        return parsed

    if isinstance(parsed, list):
        parts = []
        for item in parsed:
            if isinstance(item, dict):
                name = item.get("use_case") or item.get("name") or "Opportunity"
                priority = item.get("priority", "")
                timeline = item.get("timeline", "")
                evidence = item.get("evidence", "")
                impact = item.get("business_impact") or item.get("impact", "")

                parts.append("### {}".format(name))
                badges = []
                if priority:
                    badges.append("**Priority:** {}".format(priority.capitalize()))
                if timeline:
                    badges.append("**Timeline:** {}".format(timeline))
                if badges:
                    parts.append(" | ".join(badges))
                if evidence:
                    parts.append("**Evidence:** {}".format(evidence))
                if impact:
                    parts.append("**Business Impact:** {}".format(impact))
                parts.append("")
            elif isinstance(item, str):
                parts.append("- {}".format(item))
        return "\n".join(parts).rstrip()

    return str(parsed)


def _format_quick_wins(raw):
    """Format quick_wins into structured markdown subsections.

    Each quick win gets a heading with complexity/timeline/ROI badges
    and impact/evidence as bullet points.
    """
    parsed = _parse_structured(raw)
    if not parsed:
        return ""

    if isinstance(parsed, str):
        return parsed

    if isinstance(parsed, list):
        parts = []
        for item in parsed:
            if isinstance(item, dict):
                name = (
                    item.get("use_case")
                    or item.get("name")
                    or item.get("action")
                    or "Quick Win"
                )
                complexity = item.get("complexity", "")
                timeline = item.get("timeline", "")
                roi = item.get("roi_estimate") or item.get("roi", "")
                impact = item.get("impact", "")
                evidence = item.get("evidence", "")

                parts.append("### {}".format(name))
                badges = []
                if complexity:
                    badges.append("**Complexity:** {}".format(complexity.capitalize()))
                if timeline:
                    badges.append("**Timeline:** {}".format(timeline))
                if roi:
                    badges.append("**ROI:** {}/year".format(roi))
                if badges:
                    parts.append(" | ".join(badges))
                if impact:
                    parts.append("- **Impact:** {}".format(impact))
                if evidence:
                    parts.append("- **Evidence:** {}".format(evidence))
                parts.append("")
            elif isinstance(item, str):
                parts.append("- {}".format(item))
        return "\n".join(parts).rstrip()

    return str(parsed)


# Industry-specific persona templates keyed by common industry slugs
_INDUSTRY_PERSONAS = {
    "financial_services": [
        ("CTO / VP Engineering", "Legacy system modernization, regulatory compliance"),
        ("Head of Payments / VP Product", "Transaction speed, fraud prevention"),
        ("CISO / Head of Compliance", "Data security, audit readiness"),
    ],
    "finance": [
        ("CTO / VP Engineering", "Legacy system modernization, regulatory compliance"),
        ("Head of Payments / VP Product", "Transaction speed, fraud prevention"),
        ("CISO / Head of Compliance", "Data security, audit readiness"),
    ],
    "technology": [
        ("VP Engineering / CTO", "Developer productivity, platform scalability"),
        ("VP Product", "Feature velocity, competitive differentiation"),
        ("Head of Data / ML", "Data infrastructure, model deployment"),
    ],
    "saas": [
        ("VP Engineering / CTO", "Developer productivity, platform scalability"),
        ("VP Product", "Feature velocity, customer retention"),
        ("Head of Growth / CMO", "Acquisition cost, conversion optimization"),
    ],
    "healthcare": [
        ("CTO / VP Engineering", "Interoperability, HIPAA compliance"),
        ("CMO / VP Clinical", "Clinical workflow efficiency, patient outcomes"),
        ("VP Operations", "Cost reduction, process automation"),
    ],
    "insurance": [
        ("Chief Underwriting Officer", "Risk assessment, pricing accuracy"),
        ("VP Claims / Head of Claims", "Claims efficiency, fraud detection"),
        ("CTO / VP Engineering", "Digital transformation, legacy modernization"),
    ],
    "retail": [
        (
            "VP Digital / Head of E-Commerce",
            "Online conversion, omnichannel experience",
        ),
        ("Head of Supply Chain / VP Operations", "Inventory optimization, logistics"),
        ("CMO / VP Marketing", "Customer acquisition, brand engagement"),
    ],
    "manufacturing": [
        ("VP Operations / COO", "Production efficiency, quality control"),
        ("CTO / VP Engineering", "Automation, IoT integration"),
        ("Head of Supply Chain", "Supplier management, demand forecasting"),
    ],
    "energy": [
        ("VP Operations / COO", "Asset management, operational efficiency"),
        ("CTO / VP Engineering", "Grid modernization, data infrastructure"),
        ("Chief Sustainability Officer", "Emissions reduction, ESG compliance"),
    ],
    "education": [
        ("CTO / VP Engineering", "Platform scalability, data privacy"),
        ("VP Academic Affairs / Provost", "Curriculum delivery, student outcomes"),
        ("Head of EdTech / VP Digital Learning", "Learning platforms, engagement"),
    ],
}

_DEFAULT_PERSONAS = [
    ("CTO / VP Engineering", "Technical infrastructure, team productivity"),
    ("VP Product / Head of Product", "Feature roadmap, competitive positioning"),
    ("VP Operations / COO", "Process efficiency, cost optimization"),
]

# Maps industry substrings to canonical _INDUSTRY_PERSONAS keys.
# Checked in order; first match wins.
_INDUSTRY_FAMILIES = {
    "health": "healthcare",
    "medical": "healthcare",
    "pharma": "healthcare",
    "biotech": "healthcare",
    "life_sci": "healthcare",
    "insur": "insurance",
    "fintech": "financial_services",
    "banking": "financial_services",
    "finance": "financial_services",
    "retail": "retail",
    "ecommerce": "retail",
    "e_commerce": "retail",
    "manufactur": "manufacturing",
    "energy": "energy",
    "utilit": "energy",
    "education": "education",
    "edtech": "education",
}


def _match_industry_personas(industry_key: str) -> list:
    """Match industry to buyer personas with fuzzy prefix matching.

    Tries exact match first, then falls back to substring matching
    against ``_INDUSTRY_FAMILIES`` so that variants like
    ``health_insurance`` or ``healthcare_services`` resolve to the
    canonical ``healthcare`` persona set.
    """
    if not industry_key:
        return _DEFAULT_PERSONAS

    # Exact match first
    if industry_key in _INDUSTRY_PERSONAS:
        return _INDUSTRY_PERSONAS[industry_key]

    # Substring matching for industry families
    for prefix, canonical in _INDUSTRY_FAMILIES.items():
        if prefix in industry_key:
            if canonical in _INDUSTRY_PERSONAS:
                return _INDUSTRY_PERSONAS[canonical]

    return _DEFAULT_PERSONAS


def _parse_leadership_team(raw):
    """Parse leadership_team string into a dict mapping role keywords to names.

    Handles formats like:
    - "Patrick Collison (CEO), John Collison (President)"
    - "CEO: Patrick Collison, CTO: David Singleton"
    - "Patrick Collison - CEO, John Collison - President"

    Returns:
        dict: Mapping of lowercase role keywords to full "Name (Role)" strings.
        E.g. {"ceo": "Patrick Collison", "cto": "David Singleton"}
    """
    if not raw or not isinstance(raw, str):
        return {}

    leader_map = {}
    # Split on comma or semicolon
    entries = [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]
    for entry in entries:
        name = ""
        role = ""
        # Format: "Name (Role)"
        if "(" in entry and ")" in entry:
            paren_start = entry.index("(")
            paren_end = entry.index(")")
            name = entry[:paren_start].strip()
            role = entry[paren_start + 1 : paren_end].strip()
        # Format: "Role: Name"
        elif ":" in entry:
            parts = entry.split(":", 1)
            role = parts[0].strip()
            name = parts[1].strip()
        # Format: "Name - Role"
        elif " - " in entry:
            parts = entry.split(" - ", 1)
            name = parts[0].strip()
            role = parts[1].strip()
        else:
            continue

        if name and role:
            # Index by each word in the role for flexible matching
            role_lower = role.lower()
            for keyword in role_lower.split():
                # Strip common noise words
                if keyword not in ("of", "the", "and", "&", "for", "/"):
                    leader_map[keyword] = name
            # Also store the full role
            leader_map[role_lower] = name

    return leader_map


# Role keywords that map persona title fragments to leadership role keywords
_ROLE_KEYWORDS = {
    "cto": ["cto", "chief technology"],
    "ceo": ["ceo", "chief executive"],
    "cfo": ["cfo", "chief financial"],
    "coo": ["coo", "chief operating"],
    "cmo": ["cmo", "chief marketing"],
    "ciso": ["ciso", "chief information security"],
    "vp engineering": ["vp engineering", "engineering"],
    "vp product": ["vp product", "product"],
    "vp operations": ["vp operations", "operations"],
    "head of data": ["head of data", "data"],
    "president": ["president"],
}


def _match_leader_to_persona(persona_title, leader_map):
    """Match a persona title to a real leader from the leadership map.

    Args:
        persona_title: E.g. "CTO / VP Engineering"
        leader_map: Dict from _parse_leadership_team

    Returns:
        str or None: Leader name if matched, e.g. "David Singleton (CTO)"
    """
    if not leader_map or not persona_title:
        return None

    title_lower = persona_title.lower()

    # Extract role fragments from the persona title (split on " / " and ",")
    fragments = []
    for sep in [" / ", ", ", " or "]:
        if sep in title_lower:
            fragments.extend(title_lower.split(sep))
    if not fragments:
        fragments = [title_lower]

    for fragment in fragments:
        fragment = fragment.strip()
        # Try direct keyword matches
        for key, aliases in _ROLE_KEYWORDS.items():
            if any(alias in fragment for alias in aliases):
                # Check if this keyword exists in leader_map
                if key in leader_map:
                    return leader_map[key]
                # Also try individual words
                for alias in aliases:
                    for word in alias.split():
                        if word in leader_map:
                            return leader_map[word]

    return None


def build_seeded_template(objective=None, enrichment_data=None):
    """Generate a markdown template for a new strategy document.

    Produces a professional strategy document with structured formatting:
    - Complex enrichment fields (ai_opportunities, quick_wins) are parsed
      from JSON and formatted as subsections with badges
    - Industry names are cleaned from snake_case to Title Case
    - Each section uses distinct enrichment fields (no duplication)
    - Placeholder instructions are replaced with actionable content

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
    industry_raw = _get(co, "industry")
    industry = _clean_industry(industry_raw)
    industry_category = _clean_industry(_get(co, "industry_category"))
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

    # L2 fields
    company_overview = _get(enrichment_data, "company_overview")
    ai_opportunities_raw = enrichment_data.get("ai_opportunities") or ""
    pain_hypothesis = _get(enrichment_data, "pain_hypothesis")
    quick_wins_raw = enrichment_data.get("quick_wins") or ""

    # Signals fields
    digital_initiatives = _get(enrichment_data, "digital_initiatives")
    hiring_signals = _get(enrichment_data, "hiring_signals")
    ai_adoption_level = _get(enrichment_data, "ai_adoption_level")
    growth_indicators = _get(enrichment_data, "growth_indicators")

    # Market fields
    recent_news = _get(enrichment_data, "recent_news")
    funding_history = _get(enrichment_data, "funding_history")

    # Pre-format complex fields
    ai_opportunities_formatted = _format_opportunities(ai_opportunities_raw)
    quick_wins_formatted = _format_quick_wins(quick_wins_raw)

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
        if industry_category and industry_category.lower() != industry.lower():
            line += " ({})".format(industry_category)
        exec_parts.append(line)
    if company_size:
        line = "**Size:** {} employees".format(company_size)
        if revenue_range:
            line += " | **Revenue:** {}".format(revenue_range)
        exec_parts.append(line)
    if hq_city and hq_country:
        exec_parts.append("**HQ:** {}, {}".format(hq_city, hq_country))
    # Prefer richer L2 descriptions over basic L1 summary
    description = company_overview or company_intel or summary or ""
    if description:
        exec_parts.append("")
        exec_parts.append(description)
    # Include summary as supplemental context if it differs from the chosen description
    if summary and summary != description:
        exec_parts.append("")
        exec_parts.append(summary)
    if recent_news:
        exec_parts.append("")
        exec_parts.append("**Recent Developments:** {}".format(recent_news))
    if funding_history:
        exec_parts.append("")
        exec_parts.append("**Funding:** {}".format(funding_history))
    exec_summary = "\n".join(exec_parts)

    # --- ICP ---
    icp_parts = []
    if industry:
        icp_parts.append("**Industry:** {}".format(industry))
    if company_size:
        icp_parts.append("**Company Size:** {} employees".format(company_size))
    if revenue_range:
        icp_parts.append("**Revenue Range:** {}".format(revenue_range))
    if hq_city and hq_country:
        icp_parts.append("**Geography:** {}, {}".format(hq_city, hq_country))
    if customer_segments:
        icp_parts.append("")
        icp_parts.append("**Target Segments:** {}".format(customer_segments))
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

    # Parse leadership_team to map real leaders to persona roles
    leader_map = _parse_leadership_team(leadership_team)

    if leadership_team:
        persona_parts.append("**Key Decision-Makers:** {}".format(leadership_team))
        persona_parts.append("")
    if ai_adoption_level:
        persona_parts.append("**AI Adoption Level:** {}".format(ai_adoption_level))
        persona_parts.append("")

    # Generate industry-specific persona templates, enriched with real leaders
    industry_key = industry_raw.lower() if industry_raw else ""
    personas = _match_industry_personas(industry_key)
    for title, focus in personas:
        # Check if any known leader matches this persona role
        matched_leader = _match_leader_to_persona(title, leader_map)
        if matched_leader:
            persona_parts.append("### {} — {}".format(title, matched_leader))
        else:
            persona_parts.append("### {}".format(title))
        persona_parts.append("**Focus Areas:** {}".format(focus))
        persona_parts.append("**Pain Points:** _Fill based on discovery calls_")
        persona_parts.append("**Goals:** _Fill based on discovery calls_")
        persona_parts.append("")
    persona_content = "\n".join(persona_parts).rstrip()

    # --- Value Proposition ---
    value_parts = []
    if key_products:
        value_parts.append("**Products/Services:** {}".format(key_products))
    if pain_hypothesis:
        value_parts.append("")
        value_parts.append("**Pain Points Identified:**")
        value_parts.append("")
        value_parts.append(pain_hypothesis)
    if ai_opportunities_formatted:
        value_parts.append("")
        value_parts.append("**AI/Tech Opportunities:**")
        value_parts.append("")
        value_parts.append(ai_opportunities_formatted)
    elif company_name:
        # Contextual placeholder when AI opportunities synthesis is missing
        # Use available data to create a more specific prompt than generic text
        value_parts.append("")
        value_parts.append("**AI/Tech Opportunities:**")
        value_parts.append("")
        context_hints = []
        if industry:
            context_hints.append("the {} industry".format(industry))
        if key_products:
            context_hints.append("their product lines ({})".format(key_products))
        if recent_news:
            context_hints.append("recent developments")
        if context_hints:
            value_parts.append(
                "_Research needed: Identify AI/automation opportunities "
                "specific to {} and {}._".format(company_name, ", ".join(context_hints))
            )
        else:
            value_parts.append(
                "_Research needed: Identify AI/automation opportunities "
                "specific to {}._".format(company_name)
            )
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
        comp_parts.append(
            "Identify key competitors, their strengths and weaknesses, "
            "and your differentiation strategy."
        )
    comp_content = "\n".join(comp_parts)

    # --- Channel Strategy ---
    channel_parts = []
    if customer_segments:
        channel_parts.append("**Target Audience:** {}".format(customer_segments))
        channel_parts.append("")
    channel_parts.append("**Recommended Channels:**")
    channel_parts.append("")
    channel_parts.append(
        "- **LinkedIn** \u2014 Direct outreach to decision-makers, "
        "thought leadership content"
    )
    channel_parts.append(
        "- **Industry Events** \u2014 Conferences, meetups, "
        "and roundtables in the {} space".format(industry or "target")
    )
    channel_parts.append(
        "- **Partnerships** \u2014 Warm introductions through "
        "ecosystem partners and advisors"
    )
    if hiring_signals:
        channel_parts.append("")
        channel_parts.append(
            "**Timing Signal:** Companies actively hiring for "
            "the following roles may be in a buying window:"
        )
        channel_parts.append("")
        channel_parts.append(hiring_signals)
    channel_content = "\n".join(channel_parts)

    # --- Messaging Framework ---
    msg_parts = []
    if pain_hypothesis:
        msg_parts.append("**Lead with Pain Points:**")
        msg_parts.append("")
        msg_parts.append(pain_hypothesis)
        msg_parts.append("")
    if ai_opportunities_formatted:
        msg_parts.append("**Position AI-Powered Solutions:**")
        msg_parts.append("")
        msg_parts.append(ai_opportunities_formatted)
        msg_parts.append("")
    if tech_stack:
        msg_parts.append("**Technical Context:**")
        msg_parts.append("")
        msg_parts.append(
            "Tailor messaging to their stack ({}). Reference integration "
            "points and technical compatibility.".format(tech_stack)
        )
        msg_parts.append("")
    msg_parts.append(
        "**Proof Points:** Reference case studies and quantified results "
        "from similar {} companies to build credibility.".format(industry or "industry")
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
    if quick_wins_formatted:
        action_parts.append("### Days 1-30: Quick Wins")
        action_parts.append("")
        action_parts.append(quick_wins_formatted)
        action_parts.append("")
    else:
        action_parts.append("### Days 1-30: Foundation")
        action_parts.append("")
        action_parts.append("- Validate ICP assumptions with 5-10 discovery calls")
        action_parts.append("- Set up outreach infrastructure and sequences")
        action_parts.append("- Launch initial LinkedIn campaigns")
        action_parts.append("")
    action_parts.append("### Days 31-60: Scale")
    action_parts.append("")
    action_parts.append("- Expand outreach volume based on Day 1-30 learnings")
    action_parts.append("- A/B test messaging angles and subject lines")
    action_parts.append("- Build pipeline of qualified opportunities")
    if hiring_signals:
        action_parts.append(
            "- Monitor hiring signals for timing outreach: {}".format(hiring_signals)
        )
    action_parts.append("")
    action_parts.append("### Days 61-90: Optimize")
    action_parts.append("")
    action_parts.append("- Analyze conversion metrics and double down on top channels")
    action_parts.append("- Refine personas based on actual buyer conversations")
    action_parts.append("- Set targets for next quarter based on results")
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

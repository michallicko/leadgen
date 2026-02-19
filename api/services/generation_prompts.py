"""Prompt templates for message generation.

Each channel has constraints and a prompt template that gets filled with
enrichment data and generation config.
"""

# Channel-specific constraints
CHANNEL_CONSTRAINTS = {
    "linkedin_connect": {
        "max_chars": 300,
        "has_subject": False,
        "description": "LinkedIn connection request message (max 300 characters)",
    },
    "linkedin_message": {
        "max_chars": 2000,
        "has_subject": False,
        "description": "LinkedIn direct message",
    },
    "email": {
        "max_chars": 5000,
        "has_subject": True,
        "description": "Email with subject line and body",
    },
    "call": {
        "max_chars": 2000,
        "has_subject": False,
        "description": "Phone call script",
    },
}

SYSTEM_PROMPT = """You are an expert B2B outreach copywriter. You write personalized, \
concise outreach messages that feel human-written, not AI-generated. \
You avoid cliches, buzzwords, and generic pitches. Every message references \
specific details about the recipient and their company to show genuine research."""


FORMALITY_INSTRUCTIONS = {
    "cs": {"formal": "Use formal address (vykání – Vy).", "informal": "Use informal address (tykání – ty)."},
    "de": {"formal": "Use formal address (Sie).", "informal": "Use informal address (du)."},
    "fr": {"formal": "Use formal address (vous).", "informal": "Use informal address (tu)."},
    "es": {"formal": "Use formal address (usted).", "informal": "Use informal address (tú)."},
    "it": {"formal": "Use formal address (Lei).", "informal": "Use informal address (tu)."},
    "pt": {"formal": "Use formal address (o senhor/a senhora).", "informal": "Use informal address (você/tu)."},
    "pl": {"formal": "Use formal address (Pan/Pani).", "informal": "Use informal address (ty)."},
    "nl": {"formal": "Use formal address (u).", "informal": "Use informal address (je/jij)."},
}


def build_generation_prompt(
    *,
    channel: str,
    step_label: str,
    contact_data: dict,
    company_data: dict,
    enrichment_data: dict,
    generation_config: dict,
    step_number: int,
    total_steps: int,
    formality: str | None = None,
    per_message_instruction: str | None = None,
) -> str:
    """Build the user prompt for generating a single message step.

    Returns the prompt string to send to Claude.
    """
    constraints = CHANNEL_CONSTRAINTS.get(channel, CHANNEL_CONSTRAINTS["email"])
    tone = generation_config.get("tone", "professional")
    language = generation_config.get("language", "en")
    custom_instructions = generation_config.get("custom_instructions", "")

    # Build context sections
    contact_section = _build_contact_section(contact_data, enrichment_data)
    company_section = _build_company_section(company_data, enrichment_data)

    # Build format instructions
    if constraints["has_subject"]:
        format_instructions = (
            "Return JSON with two fields: "
            '{"subject": "...", "body": "..."}\n'
            f"Keep the subject under 60 characters.\n"
            f"Keep the body under {constraints['max_chars']} characters."
        )
    else:
        format_instructions = (
            "Return JSON with one field: "
            '{"body": "..."}\n'
            f"Keep the body under {constraints['max_chars']} characters."
        )

    parts = [
        f"Generate a {constraints['description']} for the following contact.",
        "",
        f"--- CONTACT ---",
        contact_section,
        "",
        f"--- COMPANY ---",
        company_section,
        "",
        f"--- SEQUENCE CONTEXT ---",
        f"This is step {step_number} of {total_steps}: {step_label}",
        f"Channel: {channel.replace('_', ' ')}",
        f"Tone: {tone}",
        f"Language: {language}",
    ]

    # Formality instruction (language-specific address form)
    effective_formality = formality or generation_config.get("formality")
    if effective_formality and language in FORMALITY_INSTRUCTIONS:
        fi = FORMALITY_INSTRUCTIONS[language].get(effective_formality, "")
        if fi:
            parts.append(f"Formality: {fi}")

    parts.extend([
        "",
        f"--- OUTPUT FORMAT ---",
        format_instructions,
        "Return ONLY the JSON object, no markdown fencing or explanation.",
    ])

    if custom_instructions:
        parts.extend([
            "",
            f"--- ADDITIONAL INSTRUCTIONS ---",
            custom_instructions[:2000],
        ])

    if per_message_instruction:
        parts.extend([
            "",
            f"--- PER-MESSAGE INSTRUCTION ---",
            per_message_instruction[:200],
        ])

    return "\n".join(parts)


def _build_contact_section(contact_data: dict, enrichment_data: dict) -> str:
    lines = []
    name = f"{contact_data.get('first_name', '')} {contact_data.get('last_name', '')}".strip()
    if name:
        lines.append(f"Name: {name}")
    if contact_data.get("job_title"):
        lines.append(f"Title: {contact_data['job_title']}")
    if contact_data.get("email_address"):
        lines.append(f"Email: {contact_data['email_address']}")
    if contact_data.get("linkedin_url"):
        lines.append(f"LinkedIn: {contact_data['linkedin_url']}")
    if contact_data.get("seniority_level"):
        lines.append(f"Seniority: {contact_data['seniority_level']}")
    if contact_data.get("department"):
        lines.append(f"Department: {contact_data['department']}")

    # Person enrichment data
    person = enrichment_data.get("person", {})
    if person.get("person_summary"):
        lines.append(f"Person Summary: {person['person_summary']}")
    if person.get("relationship_synthesis"):
        lines.append(f"Relationship: {person['relationship_synthesis']}")

    return "\n".join(lines) if lines else "No contact details available."


def _build_company_section(company_data: dict, enrichment_data: dict) -> str:
    lines = []
    if company_data.get("name"):
        lines.append(f"Company: {company_data['name']}")
    if company_data.get("domain"):
        lines.append(f"Domain: {company_data['domain']}")
    if company_data.get("industry"):
        lines.append(f"Industry: {company_data['industry']}")
    if company_data.get("hq_country"):
        lines.append(f"Country: {company_data['hq_country']}")
    if company_data.get("summary"):
        lines.append(f"Summary: {company_data['summary']}")

    # L2 enrichment data
    l2 = enrichment_data.get("l2", {})
    if l2.get("company_intel"):
        lines.append(f"Intel: {l2['company_intel']}")
    if l2.get("recent_news"):
        lines.append(f"Recent News: {l2['recent_news']}")
    if l2.get("ai_opportunities"):
        lines.append(f"AI Opportunities: {l2['ai_opportunities']}")

    return "\n".join(lines) if lines else "No company details available."

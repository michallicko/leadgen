"""Layer 2: Dynamic context prompt (changes per call, not cached).

Builds the dynamic portions of the system prompt:
  - User objective
  - Current strategy document content
  - Section completeness status
  - Enrichment/research data
  - Phase-specific instructions
  - Page context hints
  - Language override
"""

from __future__ import annotations

import json
from typing import Optional

from . import STRATEGY_SECTIONS


def build_context_block(
    document,
    enrichment_data: Optional[dict] = None,
    phase: Optional[str] = None,
    page_context: Optional[str] = None,
    tenant=None,
) -> dict:
    """Build the dynamic context as a single content block (not cached).

    Args:
        document: StrategyDocument model instance.
        enrichment_data: Optional dict of company enrichment data.
        phase: Phase string (strategy, contacts, messages, campaign).
        page_context: Current page name the user is viewing.
        tenant: Tenant model instance for language settings.

    Returns:
        A content block dict with dynamic context text.
    """
    parts = []

    # User objective
    objective = getattr(document, "objective", None)
    if objective:
        parts.append("The user's stated objective: {}".format(objective))

    # Strategy document content
    content = document.content if document.content else ""
    if isinstance(content, dict):
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

        # Section completeness
        section_status = _compute_section_status(content)
        if section_status:
            parts.extend(
                [
                    "",
                    "STRATEGY COMPLETENESS STATUS:",
                    "\n".join(section_status),
                    "",
                    "Prioritize helping the user fill EMPTY and NEEDS WORK sections.",
                ]
            )
    else:
        parts.extend(
            [
                "",
                "The strategy document is currently empty. Immediately start "
                "writing sections using `update_strategy_section` — do not wait "
                "for permission.",
            ]
        )

    # Document awareness
    parts.extend(
        [
            "",
            "DOCUMENT AWARENESS (mandatory):",
            "- Always reference the strategy document content provided above.",
            "- Never ask the user to repeat information already in the document.",
            "- If the document is empty, immediately start writing sections.",
        ]
    )

    # ICP/persona status
    extracted = document.extracted_data or {}
    if isinstance(extracted, str):
        try:
            extracted = json.loads(extracted)
        except (ValueError, TypeError):
            extracted = {}
    has_tiers = bool(extracted.get("tiers"))
    has_personas = bool(extracted.get("personas"))

    if not has_tiers or not has_personas:
        missing = []
        if not has_tiers:
            missing.append("ICP tiers are currently EMPTY")
        if not has_personas:
            missing.append("Buyer personas are currently EMPTY")
        parts.append(
            "\nURGENT: {} — populate them immediately by calling the "
            "appropriate tool(s).".format(" and ".join(missing))
        )

    # Enrichment data
    if enrichment_data:
        parts.extend(_format_enrichment(enrichment_data))
    else:
        parts.extend(
            [
                "",
                "--- Company Research Status ---",
                "No company research data available yet.",
                "--- End of Research Status ---",
            ]
        )

    # Phase instructions
    active_phase = phase or getattr(document, "phase", "strategy") or "strategy"
    phase_text = _get_phase_instructions(active_phase)
    if phase_text:
        parts.extend(["", "--- Phase-Specific Instructions ---", phase_text])

    # Page context hints
    if page_context and page_context != "playbook":
        hint = _get_page_hint(page_context)
        if hint:
            parts.extend(
                [
                    "",
                    "--- Current Page Context ---",
                    "The user is currently on the '{}' page.".format(page_context),
                    hint,
                ]
            )

    # Language override
    if tenant:
        _append_language(parts, tenant)

    return {
        "type": "text",
        "text": "\n".join(parts),
    }


def _compute_section_status(content: str) -> list[str]:
    """Compute completeness status for each strategy section."""
    status = []
    for section_name in STRATEGY_SECTIONS:
        heading = "## {}".format(section_name)
        if heading in content:
            idx = content.index(heading)
            next_heading = content.find("\n## ", idx + len(heading))
            if next_heading == -1:
                section_content = content[idx + len(heading) :]
            else:
                section_content = content[idx + len(heading) : next_heading]
            lines = [
                ln.strip() for ln in section_content.strip().split("\n") if ln.strip()
            ]
            word_count = sum(len(ln.split()) for ln in lines)
            if word_count < 20:
                status.append(
                    "- {} [NEEDS WORK -- only {} words]".format(
                        section_name, word_count
                    )
                )
            elif word_count < 80:
                status.append(
                    "- {} [PARTIAL -- {} words]".format(section_name, word_count)
                )
            else:
                status.append(
                    "- {} [COMPLETE -- {} words]".format(section_name, word_count)
                )
        else:
            status.append("- {} [EMPTY -- not yet written]".format(section_name))
    return status


def _format_enrichment(enrichment_data: dict) -> list[str]:
    """Format enrichment data for the context prompt.

    Delegates to the existing _format_enrichment_for_prompt in playbook_service.
    """
    # Import lazily to avoid circular imports
    from ...services.playbook_service import _format_enrichment_for_prompt

    return _format_enrichment_for_prompt(enrichment_data)


def _get_phase_instructions(phase: str) -> str:
    """Get phase-specific instructions text."""
    from ...services.playbook_service import PHASE_INSTRUCTIONS

    return PHASE_INSTRUCTIONS.get(phase, "")


def _get_page_hint(page_context: str) -> Optional[str]:
    """Get page context hint text."""
    from ...services.playbook_service import PAGE_CONTEXT_HINTS

    return PAGE_CONTEXT_HINTS.get(page_context)


def _append_language(parts: list[str], tenant) -> None:
    """Append language override instructions if needed."""
    try:
        from ...services.language import get_effective_language
        from ...display import LANGUAGE_NAMES

        lang = get_effective_language(tenant)
        if lang and lang != "en":
            lang_name = LANGUAGE_NAMES.get(lang, lang)
            parts.extend(
                [
                    "",
                    "--- Language ---",
                    "IMPORTANT: Respond in {}. ".format(lang_name)
                    + "Strategy document section titles may stay in English, "
                    + "but all conversational text must be in {}.".format(lang_name),
                ]
            )
    except (ImportError, AttributeError):
        pass

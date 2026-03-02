"""Strategy document tool handlers for AI chat tool-use.

Each handler:
1. Creates a version snapshot (before edit)
2. Performs the edit
3. Increments document version
4. Commits to DB
5. Returns a result dict for the AI

Registered with the AGENT tool registry at app startup.
"""

from __future__ import annotations

import json
import logging
import re

from ..models import StrategyDocument, StrategyVersion, db
from .tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)


# -- Known sections: must match the H2 headings in build_seeded_template() --
KNOWN_SECTIONS = [
    "Executive Summary",
    "Ideal Customer Profile (ICP)",
    "Buyer Personas",
    "Value Proposition & Messaging",
    "Competitive Positioning",
    "Channel Strategy",
    "Messaging Framework",
    "Metrics & KPIs",
    "90-Day Action Plan",
]

# Extraction schema paths that the AI can set
EXTRACTED_DATA_SCHEMA = {
    "icp": {
        "industries",
        "company_size",
        "geographies",
        "tech_signals",
        "triggers",
        "disqualifiers",
    },
    "personas": None,  # array of objects -- validated structurally
    "messaging": {"tone", "themes", "angles", "proof_points"},
    "channels": {"primary", "secondary", "cadence"},
    "metrics": {
        "reply_rate_target",
        "meeting_rate_target",
        "pipeline_goal_eur",
        "timeline_months",
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _snapshot(doc, edit_source="ai_tool", turn_id=None):
    """Create a StrategyVersion snapshot before modifying the document.

    Args:
        doc: StrategyDocument instance.
        edit_source: "ai_tool", "user_undo", or "manual".
        turn_id: The strategy_chat_messages.id of the assistant message
            that triggered this tool call. All snapshots from one agent
            turn share the same turn_id.
    """
    snap = StrategyVersion(
        document_id=doc.id,
        tenant_id=doc.tenant_id,
        version=doc.version,
        content=doc.content,
        extracted_data=doc.extracted_data,
        edit_source=edit_source,
        turn_id=turn_id,
    )
    db.session.add(snap)
    return snap


def _find_section(content, section_name):
    """Find a section in markdown by its H2 heading.

    Returns ``(start_of_body, end_of_body)`` character offsets, or ``None``
    if the heading is not found.  ``start_of_body`` is the first character
    of the line after the heading.  ``end_of_body`` is the character
    position just before the next H2 heading (or end of document).
    """
    pattern = r"^## " + re.escape(section_name) + r"\s*$"
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return None

    # Body starts after the heading line
    body_start = match.end()
    if body_start < len(content) and content[body_start] == "\n":
        body_start += 1  # skip the newline after heading

    # Body ends at the next H2 heading or end of document
    next_h2 = re.search(r"^## ", content[body_start:], re.MULTILINE)
    if next_h2:
        body_end = body_start + next_h2.start()
    else:
        body_end = len(content)

    return (body_start, body_end)


def _set_nested(obj, path, value):
    """Set a value at a dot-notation path in a nested dict/list.

    Supports array indexing with ``[N]``, e.g. ``"personas[0].title"``.
    Creates intermediate dicts as needed.  Raises ``KeyError`` on invalid
    array index access.
    """
    # Split path into tokens, e.g. "personas[0].title" -> ["personas", "[0]", "title"]
    tokens = re.split(r"\.|\[(\d+)\]", path)
    tokens = [t for t in tokens if t is not None and t != ""]

    current = obj
    for i, token in enumerate(tokens[:-1]):
        if token.isdigit():
            idx = int(token)
            if not isinstance(current, list) or idx >= len(current):
                raise KeyError("Invalid index [{}] at path position {}".format(idx, i))
            current = current[idx]
        else:
            if token not in current:
                current[token] = {}
            current = current[token]

    # Set the final value
    final = tokens[-1]
    if final.isdigit():
        idx = int(final)
        if not isinstance(current, list) or idx >= len(current):
            raise KeyError("Invalid index [{}]".format(idx))
        current[idx] = value
    else:
        current[final] = value


def _format_sections_list():
    """Return a formatted string of available section names."""
    return ", ".join("'{}'".format(s) for s in KNOWN_SECTIONS)


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def get_strategy_document(args: dict, ctx: ToolContext) -> dict:
    """Handler for get_strategy_document tool.

    Returns the current strategy document content, extracted data,
    version number, and last-updated timestamp.
    """
    doc = StrategyDocument.query.filter_by(tenant_id=ctx.tenant_id).first()
    if not doc:
        return {"error": "No strategy document found"}
    return {
        "content": doc.content or "",
        "extracted_data": doc.extracted_data or {},
        "version": doc.version,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def update_strategy_section(args: dict, ctx: ToolContext) -> dict:
    """Handler for update_strategy_section tool.

    Replaces the body of a named H2 section in the markdown document.
    Creates a version snapshot before editing.
    """
    section = args.get("section", "")
    new_content = args.get("content", "")

    doc = StrategyDocument.query.filter_by(tenant_id=ctx.tenant_id).first()
    if not doc:
        return {"error": "No strategy document found"}

    doc_content = doc.content or ""

    # Validate section name
    if section not in KNOWN_SECTIONS:
        return {
            "error": "Section '{}' not found. Available sections: {}".format(
                section, _format_sections_list()
            )
        }

    # Create snapshot before edit
    _snapshot(doc, turn_id=getattr(ctx, "turn_id", None))

    previous_version = doc.version

    bounds = _find_section(doc_content, section)
    if bounds is None:
        # Section heading not found — append new section to end of document
        separator = "\n\n" if doc_content.strip() else ""
        doc.content = (
            doc_content.rstrip()
            + separator
            + "## "
            + section
            + "\n\n"
            + new_content.strip()
            + "\n"
        )
    else:
        start, end = bounds
        # Replace section body
        new_body = "\n" + new_content.strip() + "\n\n"
        doc.content = doc_content[:start] + new_body + doc_content[end:]

    doc.version += 1
    doc.updated_by = ctx.user_id
    db.session.commit()

    return {
        "success": True,
        "section": section,
        "version": doc.version,
        "previous_version": previous_version,
    }


def set_extracted_field(args: dict, ctx: ToolContext) -> dict:
    """Handler for set_extracted_field tool.

    Updates a field in the extracted_data JSONB column at the given
    dot-notation path.  Creates a version snapshot before editing.
    """
    path = args.get("path", "")
    value = args.get("value")

    doc = StrategyDocument.query.filter_by(tenant_id=ctx.tenant_id).first()
    if not doc:
        return {"error": "No strategy document found"}

    # Create snapshot before edit
    _snapshot(doc, turn_id=getattr(ctx, "turn_id", None))

    extracted = doc.extracted_data or {}
    if isinstance(extracted, str):
        extracted = json.loads(extracted)

    # Navigate dot-notation path and set value
    try:
        _set_nested(extracted, path, value)
    except (KeyError, TypeError) as exc:
        # Roll back the snapshot since no edit happened
        db.session.rollback()
        return {"error": "Invalid path '{}': {}".format(path, str(exc))}

    doc.extracted_data = extracted
    doc.version += 1
    doc.updated_by = ctx.user_id
    db.session.commit()

    return {
        "success": True,
        "path": path,
        "value": value,
        "version": doc.version,
    }


def track_assumption(args: dict, ctx: ToolContext) -> dict:
    """Handler for track_assumption tool.

    Records or updates an assumption in the strategy document's
    extracted_data.assumptions array.  Each assumption has an id, text,
    status (open/validated/invalidated), source, and is associated with
    a discovery_round counter.
    """
    assumption_id = args.get("assumption_id", "")
    text = args.get("text", "")
    status = args.get("status", "open")
    source = args.get("source", "")

    if status not in ("open", "validated", "invalidated"):
        return {"error": "status must be 'open', 'validated', or 'invalidated'"}

    if not assumption_id or not text:
        return {"error": "assumption_id and text are required"}

    doc = StrategyDocument.query.filter_by(tenant_id=ctx.tenant_id).first()
    if not doc:
        return {"error": "No strategy document found"}

    # Create snapshot before edit
    _snapshot(doc, turn_id=getattr(ctx, "turn_id", None))

    try:
        extracted = doc.extracted_data or {}
        if isinstance(extracted, str):
            extracted = json.loads(extracted)
    except (json.JSONDecodeError, ValueError):
        db.session.rollback()
        return {"error": "Corrupt extracted_data in document"}

    # Ensure assumptions array exists
    if "assumptions" not in extracted:
        extracted["assumptions"] = []

    # Ensure discovery tracking fields exist
    if "discovery_round" not in extracted:
        extracted["discovery_round"] = 0
    if "confidence_score" not in extracted:
        extracted["confidence_score"] = 0.0

    # Find existing assumption by id and track previous status
    found = False
    prev_status = None
    for assumption in extracted["assumptions"]:
        if assumption.get("id") == assumption_id:
            prev_status = assumption.get("status")
            assumption["text"] = text
            assumption["status"] = status
            assumption["source"] = source
            found = True
            break

    if not found:
        extracted["assumptions"].append(
            {
                "id": assumption_id,
                "text": text,
                "status": status,
                "source": source,
            }
        )

    # Recalculate confidence score based on assumption statuses
    assumptions = extracted["assumptions"]
    if assumptions:
        resolved = sum(
            1 for a in assumptions if a.get("status") in ("validated", "invalidated")
        )
        extracted["confidence_score"] = round(resolved / len(assumptions), 2)

    # Increment discovery round only when status actually changes
    if status in ("validated", "invalidated") and prev_status != status:
        extracted["discovery_round"] = extracted.get("discovery_round", 0) + 1

    doc.extracted_data = extracted
    doc.version += 1
    doc.updated_by = ctx.user_id
    db.session.commit()

    return {
        "success": True,
        "assumption_id": assumption_id,
        "status": status,
        "total_assumptions": len(assumptions),
        "confidence_score": extracted["confidence_score"],
        "discovery_round": extracted["discovery_round"],
    }


def check_readiness(args: dict, ctx: ToolContext) -> dict:
    """Handler for check_readiness tool.

    Evaluates whether the strategy is converged enough for phase
    transition by checking extracted_data and document content for
    completeness across key dimensions.
    """
    doc = StrategyDocument.query.filter_by(tenant_id=ctx.tenant_id).first()
    if not doc:
        return {"error": "No strategy document found"}

    extracted = doc.extracted_data or {}
    if isinstance(extracted, str):
        extracted = json.loads(extracted)

    content = doc.content or ""

    gaps = []
    checks_passed = 0
    total_checks = 4

    # Check 1: ICP has specific disqualifiers
    icp = extracted.get("icp", {})
    if isinstance(icp, str):
        try:
            icp = json.loads(icp)
        except (json.JSONDecodeError, ValueError):
            icp = {}
    disqualifiers = icp.get("disqualifiers", [])
    if disqualifiers and len(disqualifiers) > 0:
        checks_passed += 1
    else:
        gaps.append("ICP needs specific disqualifiers (not just 'tech companies')")

    # Check 2: At least 2 personas defined
    personas = extracted.get("personas", [])
    if isinstance(personas, str):
        try:
            personas = json.loads(personas)
        except (json.JSONDecodeError, ValueError):
            personas = []
    if isinstance(personas, list) and len(personas) >= 2:
        checks_passed += 1
    else:
        gaps.append(
            "Define at least 2 buyer personas with title patterns "
            "(currently {})".format(len(personas) if isinstance(personas, list) else 0)
        )

    # Check 3: Messaging angles grounded in research
    messaging = extracted.get("messaging", {})
    if isinstance(messaging, str):
        try:
            messaging = json.loads(messaging)
        except (json.JSONDecodeError, ValueError):
            messaging = {}
    angles = messaging.get("angles", [])
    if angles and len(angles) > 0:
        checks_passed += 1
    else:
        gaps.append("Messaging needs specific angles grounded in research")

    # Check 4: Channel strategy has rationale
    channels = extracted.get("channels", {})
    if isinstance(channels, str):
        try:
            channels = json.loads(channels)
        except (json.JSONDecodeError, ValueError):
            channels = {}
    has_primary = bool(channels.get("primary"))
    # Also check document content for channel rationale
    has_channel_section = (
        "## Channel Strategy" in content
        and len(content.split("## Channel Strategy")[1].split("##")[0].strip()) > 50
    )
    if has_primary and has_channel_section:
        checks_passed += 1
    else:
        if not has_primary:
            gaps.append("Channel strategy needs a primary channel defined")
        if not has_channel_section:
            gaps.append(
                "Channel strategy section needs rationale (currently too brief)"
            )

    # Calculate readiness score
    score = round(checks_passed / total_checks, 2) if total_checks > 0 else 0.0

    # Factor in assumption confidence
    assumptions = extracted.get("assumptions", [])
    assumption_confidence = extracted.get("confidence_score", 0.0)
    if assumptions:
        # Weight: 60% structural checks, 40% assumption confidence
        score = round(0.6 * score + 0.4 * assumption_confidence, 2)

    ready = checks_passed == total_checks

    return {
        "ready": ready,
        "score": score,
        "checks_passed": checks_passed,
        "total_checks": total_checks,
        "gaps": gaps,
        "assumptions_tracked": len(assumptions),
        "assumption_confidence": assumption_confidence,
    }


def append_to_section(args: dict, ctx: ToolContext) -> dict:
    """Handler for append_to_section tool.

    Appends markdown content to the end of an existing section without
    replacing it.  Creates a version snapshot before editing.
    """
    section = args.get("section", "")
    new_content = args.get("content", "")

    doc = StrategyDocument.query.filter_by(tenant_id=ctx.tenant_id).first()
    if not doc:
        return {"error": "No strategy document found"}

    doc_content = doc.content or ""

    if section not in KNOWN_SECTIONS:
        return {
            "error": "Section '{}' not found. Available sections: {}".format(
                section, _format_sections_list()
            )
        }

    # Create snapshot before edit
    _snapshot(doc, turn_id=getattr(ctx, "turn_id", None))

    previous_version = doc.version

    bounds = _find_section(doc_content, section)
    if bounds is None:
        # Section heading not found — append new section to end of document
        separator = "\n\n" if doc_content.strip() else ""
        doc.content = (
            doc_content.rstrip()
            + separator
            + "## "
            + section
            + "\n\n"
            + new_content.strip()
            + "\n"
        )
    else:
        start, end = bounds
        # Append to section (after existing content, before trailing whitespace)
        existing = doc_content[start:end].rstrip()
        new_body = existing + "\n\n" + new_content.strip() + "\n\n"
        doc.content = doc_content[:start] + new_body + doc_content[end:]

    doc.version += 1
    doc.updated_by = ctx.user_id
    db.session.commit()

    return {
        "success": True,
        "section": section,
        "action": "appended",
        "version": doc.version,
        "previous_version": previous_version,
    }


# ---------------------------------------------------------------------------
# Tool definitions for registry
# ---------------------------------------------------------------------------

STRATEGY_TOOLS = [
    ToolDefinition(
        name="get_strategy_document",
        description=(
            "Read the current strategy document content and metadata. "
            "Returns the full markdown document, extracted structured data, "
            "version number, and last-updated timestamp. Use this to get a "
            "fresh copy after making edits."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=get_strategy_document,
    ),
    ToolDefinition(
        name="update_strategy_section",
        description=(
            "Replace the content of a specific section in the strategy "
            "document. The section is identified by its H2 heading name. "
            "The new content replaces everything between this heading and "
            "the next H2 heading (or end of document). Provide full "
            "markdown content for the section body -- do NOT include the "
            "H2 heading itself."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": (
                        "The H2 section heading to update. Must match an "
                        "existing heading exactly. Available sections: "
                        "'Executive Summary', 'Ideal Customer Profile (ICP)', "
                        "'Buyer Personas', 'Value Proposition & Messaging', "
                        "'Competitive Positioning', 'Channel Strategy', "
                        "'Messaging Framework', 'Metrics & KPIs', "
                        "'90-Day Action Plan'."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": (
                        "The new markdown content for this section. Do NOT "
                        "include the H2 heading line -- only the body text "
                        "below it."
                    ),
                },
            },
            "required": ["section", "content"],
        },
        handler=update_strategy_section,
    ),
    ToolDefinition(
        name="set_extracted_field",
        description=(
            "Set a structured field in the strategy's extracted data (JSONB). "
            "Used for ICP parameters, persona details, messaging config, "
            "channel settings, and metric targets. The field path uses dot "
            "notation (e.g., 'icp.industries', 'metrics.reply_rate_target', "
            "'personas[0].title_patterns')."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Dot-notation path to the field. Supports array "
                        "indexing with [N]. Examples: 'icp.industries', "
                        "'icp.company_size.min', 'personas[0].pain_points', "
                        "'metrics.reply_rate_target', 'messaging.tone'."
                    ),
                },
                "value": {
                    "description": (
                        "The new value. Can be a string, number, boolean, "
                        "array, or object depending on the field."
                    ),
                },
            },
            "required": ["path", "value"],
        },
        handler=set_extracted_field,
    ),
    ToolDefinition(
        name="append_to_section",
        description=(
            "Append markdown content to the end of an existing strategy "
            "section. Use this to add new items (pain points, personas, "
            "action items) without replacing existing content. The content "
            "is added after the last non-empty line of the section."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": (
                        "The H2 section heading to append to. Must match "
                        "an existing heading exactly."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": (
                        "Markdown content to append. Will be separated "
                        "from existing content by a blank line."
                    ),
                },
            },
            "required": ["section", "content"],
        },
        handler=append_to_section,
    ),
    ToolDefinition(
        name="track_assumption",
        description=(
            "Record or update a strategic assumption during convergent "
            "discovery. Use this to track whether key hypotheses in the "
            "Strategic Brief have been validated or invalidated through "
            "user feedback. Each assumption has an id, text, status "
            "(open/validated/invalidated), and a source citation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "assumption_id": {
                    "type": "string",
                    "description": (
                        "Unique identifier for this assumption (e.g., "
                        "'icp_mid_market', 'channel_linkedin'). Use "
                        "snake_case, descriptive names."
                    ),
                },
                "text": {
                    "type": "string",
                    "description": (
                        "The assumption text (e.g., 'Mid-market SaaS "
                        "companies (50-500 employees) are the primary ICP')."
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": ["open", "validated", "invalidated"],
                    "description": (
                        "Current status: 'open' (untested), 'validated' "
                        "(confirmed by user/data), 'invalidated' (disproven)."
                    ),
                },
                "source": {
                    "type": "string",
                    "description": (
                        "Source of validation/invalidation (e.g., "
                        "'user confirmed', 'web research', 'discovery call')."
                    ),
                },
            },
            "required": ["assumption_id", "text", "status"],
        },
        handler=track_assumption,
    ),
    ToolDefinition(
        name="check_readiness",
        description=(
            "Evaluate whether the strategy is converged enough for phase "
            "transition to Contacts. Checks: ICP has specific disqualifiers, "
            "at least 2 personas defined, messaging angles are research-grounded, "
            "and channel strategy has rationale. Returns a readiness score, "
            "boolean ready flag, and list of remaining gaps."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=check_readiness,
    ),
]

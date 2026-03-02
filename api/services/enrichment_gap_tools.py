"""Enrichment gap analysis tool handler for AI chat tool-use.

Provides one tool:
- get_enrichment_gaps: Analyzes enrichment readiness of contacts matching
  the strategy's ICP criteria, cross-referencing entity_stage_completions
  for enrichment status.

Registered with the AGENT tool registry at app startup.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from ..models import StrategyDocument, db
from .icp_filter_tools import _map_icp_to_filters, _parse_jsonb
from .tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage constants
# ---------------------------------------------------------------------------

STAGE_L1 = "l1_company"
STAGE_L2 = "l2_deep_research"
STAGE_PERSON = "person"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_filter_clauses(filters: dict, params: dict) -> list[str]:
    """Build WHERE clauses from ICP filter dict.

    Mutates ``params`` to add bind values. Returns a list of SQL fragments.
    """
    where: list[str] = []

    multi = {
        "industries": ("co.industry", "ind"),
        "seniority_levels": ("ct.seniority_level", "sen"),
        "geo_regions": ("co.geo_region", "geo"),
        "company_sizes": ("co.company_size", "csz"),
    }
    for key, (column, prefix) in multi.items():
        values = filters.get(key, [])
        if not values or not isinstance(values, list):
            continue
        phs = []
        for i, v in enumerate(values):
            pname = "{}_{}".format(prefix, i)
            params[pname] = v
            phs.append(":{}".format(pname))
        where.append("{} IN ({})".format(column, ", ".join(phs)))

    return where


def _classify_contacts(tenant_id: str, filters: dict) -> dict:
    """Query contacts matching ICP filters and classify enrichment status.

    Returns a dict with ``contacts`` (list of row dicts) and ``summary``
    (aggregated counts).
    """
    params: dict = {"tenant_id": tenant_id}
    where = [
        "ct.tenant_id = :tenant_id",
        "(ct.is_disqualified = false OR ct.is_disqualified IS NULL)",
    ]
    where.extend(_build_filter_clauses(filters, params))
    where_clause = " AND ".join(where)

    # Subquery: for each contact, check which enrichment stages are completed
    # L1 and L2 are company-level (entity_type=company, entity_id=company_id)
    # Person is contact-level (entity_type=contact, entity_id=contact_id)
    sql = """
        SELECT
            ct.id AS contact_id,
            ct.company_id,
            co.industry,
            ct.seniority_level,
            (SELECT COUNT(*) FROM entity_stage_completions esc
             WHERE esc.entity_id = ct.company_id
               AND esc.entity_type = 'company'
               AND esc.stage = :stage_l1
               AND esc.status = 'completed'
               AND esc.tenant_id = :tenant_id
            ) AS l1_done,
            (SELECT COUNT(*) FROM entity_stage_completions esc
             WHERE esc.entity_id = ct.company_id
               AND esc.entity_type = 'company'
               AND esc.stage = :stage_l2
               AND esc.status = 'completed'
               AND esc.tenant_id = :tenant_id
            ) AS l2_done,
            (SELECT COUNT(*) FROM entity_stage_completions esc
             WHERE esc.entity_id = ct.id
               AND esc.entity_type = 'contact'
               AND esc.stage = :stage_person
               AND esc.status = 'completed'
               AND esc.tenant_id = :tenant_id
            ) AS person_done
        FROM contacts ct
        LEFT JOIN companies co ON ct.company_id = co.id
        WHERE {where}
    """.format(where=where_clause)

    params["stage_l1"] = STAGE_L1
    params["stage_l2"] = STAGE_L2
    params["stage_person"] = STAGE_PERSON

    rows = db.session.execute(text(sql), params).fetchall()

    contacts = []
    summary = {
        "fully_enriched": 0,
        "needs_person": 0,
        "needs_l2": 0,
        "needs_l1": 0,
    }

    for r in rows:
        l1 = r[4] > 0  # l1_done
        l2 = r[5] > 0  # l2_done
        person = r[6] > 0  # person_done

        if l1 and l2 and person:
            category = "fully_enriched"
        elif l1 and l2 and not person:
            category = "needs_person"
        elif l1 and not l2:
            category = "needs_l2"
        else:
            category = "needs_l1"

        summary[category] += 1
        contacts.append({
            "contact_id": r[0],
            "company_id": r[1],
            "industry": r[2],
            "seniority_level": r[3],
            "category": category,
        })

    return {"contacts": contacts, "summary": summary}


def _build_segments(contacts: list[dict], group_by: list[str]) -> list[dict]:
    """Aggregate contacts into segments by the given dimensions."""
    # Build composite key for each contact
    buckets: dict[str, dict] = {}

    for ct in contacts:
        parts = []
        for dim in group_by:
            val = ct.get(dim) or "Unknown"
            parts.append(str(val))
        key = " / ".join(parts)

        if key not in buckets:
            buckets[key] = {
                "name": key,
                "total": 0,
                "fully_enriched": 0,
                "gaps": {"needs_person": 0, "needs_l2": 0, "needs_l1": 0},
            }

        buckets[key]["total"] += 1
        cat = ct["category"]
        if cat == "fully_enriched":
            buckets[key]["fully_enriched"] += 1
        else:
            buckets[key]["gaps"][cat] += 1

    # Sort by total descending
    segments = sorted(buckets.values(), key=lambda s: s["total"], reverse=True)
    return segments


def _generate_recommendations(
    total: int, summary: dict, segments: list[dict]
) -> list[str]:
    """Generate actionable recommendations based on gap analysis."""
    recs: list[str] = []

    if total == 0:
        recs.append(
            "No contacts match your current ICP criteria. "
            "Consider broadening your ICP filters or importing more contacts."
        )
        return recs

    fully = summary["fully_enriched"]
    needs_person = summary["needs_person"]
    needs_l2 = summary["needs_l2"]
    needs_l1 = summary["needs_l1"]

    # High enrichment completion
    if total > 0 and fully / total >= 0.8:
        recs.append(
            "{} of {} contacts ({:.0f}%) are fully enriched. "
            "You're ready to proceed to message generation.".format(
                fully, total, fully / total * 100
            )
        )

    # >30% need person enrichment
    if total > 0 and needs_person / total > 0.3:
        recs.append(
            "{} contacts ({:.0f}%) have company data but need person enrichment. "
            "Run person enrichment to unlock personalized messaging.".format(
                needs_person, needs_person / total * 100
            )
        )

    # >30% need L2
    if total > 0 and needs_l2 / total > 0.3:
        recs.append(
            "{} contacts ({:.0f}%) need deep research (L2). "
            "Run L2 enrichment to get detailed company intelligence.".format(
                needs_l2, needs_l2 / total * 100
            )
        )

    # >30% need L1
    if total > 0 and needs_l1 / total > 0.3:
        recs.append(
            "{} contacts ({:.0f}%) have no enrichment data. "
            "Start with L1 company enrichment.".format(
                needs_l1, needs_l1 / total * 100
            )
        )

    # Check for specific segments with high gap rates
    for seg in segments[:5]:
        if seg["total"] >= 3:
            gap_total = sum(seg["gaps"].values())
            if seg["total"] > 0 and gap_total / seg["total"] > 0.5:
                recs.append(
                    "Segment '{}' has {} of {} contacts ({:.0f}%) with "
                    "enrichment gaps — prioritize this segment.".format(
                        seg["name"],
                        gap_total,
                        seg["total"],
                        gap_total / seg["total"] * 100,
                    )
                )

    # Low total matches
    if total < 10:
        recs.append(
            "Only {} contacts match your ICP. Consider broadening "
            "your criteria or importing more contacts.".format(total)
        )

    # If no recommendations generated (edge case), add a generic one
    if not recs:
        recs.append(
            "Review your enrichment coverage and consider running "
            "enrichment on contacts with gaps."
        )

    return recs


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------


def get_enrichment_gaps(args: dict, ctx: ToolContext) -> dict:
    """Analyze enrichment readiness of contacts matching the strategy's ICP.

    Cross-references the strategy's extracted_data.icp for contact filtering
    with entity_stage_completions for enrichment status.
    """
    strategy_id = args.get("strategy_id")
    filter_overrides = args.get("filters") or {}
    group_by = args.get("group_by") or ["industry", "seniority_level"]

    # Validate group_by dimensions
    VALID_GROUP_BY = {"industry", "seniority_level"}
    group_by = [dim for dim in group_by if dim in VALID_GROUP_BY]
    if not group_by:
        group_by = ["industry", "seniority_level"]

    # Get strategy document
    if strategy_id:
        doc = StrategyDocument.query.filter_by(
            tenant_id=ctx.tenant_id, id=strategy_id
        ).first()
    else:
        doc = StrategyDocument.query.filter_by(tenant_id=ctx.tenant_id).first()

    if not doc:
        return {"error": "No strategy document found.", "total_matches": 0}

    # Parse extracted data
    extracted = _parse_jsonb(doc.extracted_data) if doc.extracted_data else None
    if not extracted or not isinstance(extracted, dict):
        return {
            "error": "No ICP criteria found in strategy. Extract ICP data first.",
            "total_matches": 0,
        }

    icp = extracted.get("icp", {})
    if not icp or not isinstance(icp, dict):
        return {
            "error": "No ICP criteria found in strategy. Extract ICP data first.",
            "total_matches": 0,
        }

    # Merge top-level personas into icp if not already present
    top_personas = extracted.get("personas", [])
    icp_personas = icp.get("personas", [])
    if top_personas and not icp_personas:
        icp["personas"] = top_personas

    # Map ICP to filters
    filters = _map_icp_to_filters(icp)

    # Apply filter overrides (allowlisted keys only)
    ALLOWED_FILTER_KEYS = {"industries", "seniority_levels", "geo_regions", "company_sizes"}
    if filter_overrides and isinstance(filter_overrides, dict):
        for k, v in filter_overrides.items():
            if k in ALLOWED_FILTER_KEYS and isinstance(v, list) and v:
                filters[k] = v

    if not filters:
        return {
            "error": "ICP data found but no mappable filter criteria.",
            "total_matches": 0,
        }

    # Classify contacts by enrichment status
    result = _classify_contacts(ctx.tenant_id, filters)
    contacts = result["contacts"]
    summary = result["summary"]
    total = len(contacts)

    # Build segments
    segments = _build_segments(contacts, group_by)

    # Generate recommendations
    recommendations = _generate_recommendations(total, summary, segments)

    return {
        "total_matches": total,
        "enrichment_summary": summary,
        "segments": segments,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Tool definitions for registry
# ---------------------------------------------------------------------------

ENRICHMENT_TOOLS = [
    ToolDefinition(
        name="get_enrichment_gaps",
        description=(
            "Analyze enrichment readiness of contacts matching the strategy's "
            "ICP criteria. Returns a gap analysis showing how many contacts "
            "are fully enriched vs needing L1, L2, or person enrichment. "
            "Includes per-segment breakdown (by industry, seniority, etc.) "
            "and actionable recommendations. Use this when transitioning "
            "from contacts to messaging phase, or when the user wants to "
            "know which contacts are ready for outreach."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "strategy_id": {
                    "type": "string",
                    "description": (
                        "Strategy document UUID. Defaults to the tenant's "
                        "active strategy if not provided."
                    ),
                },
                "filters": {
                    "type": "object",
                    "description": (
                        "Optional filter overrides. Same structure as "
                        "filter_contacts parameters (industries, "
                        "seniority_levels, geo_regions, company_sizes)."
                    ),
                },
                "group_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Grouping dimensions for segment breakdown. "
                        "Default: ['industry', 'seniority_level']. "
                        "Available: industry, seniority_level."
                    ),
                },
            },
            "required": [],
        },
        handler=get_enrichment_gaps,
    ),
]

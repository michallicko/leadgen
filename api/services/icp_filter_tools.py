"""ICP-to-filter mapping tool handler for AI chat tool-use.

Provides one tool:
- apply_icp_filters: Reads ICP from the strategy document and maps
  criteria to contact filter parameters, returning match counts and
  a side_effect for the frontend ChatFilterSyncBar.

Registered with the AGENT tool registry at app startup.
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import text

from ..models import StrategyDocument, db
from .tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)


def _parse_jsonb(val):
    """Parse a JSONB value that may be a string in SQLite tests."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# ICP field → contact filter mapping
# ---------------------------------------------------------------------------

def _map_icp_to_filters(icp: dict) -> dict:
    """Map ICP extracted_data fields to contact filter parameters.

    ICP fields         → filter_contacts parameters
    ─────────────────────────────────────────────────
    industries         → industries (array)
    geographies        → geo_regions (array)
    company_size       → company_sizes (array of range labels)
    personas[].seniority → seniority_levels (array, deduplicated)
    """
    filters: dict = {}

    industries = icp.get("industries")
    if industries and isinstance(industries, list):
        filters["industries"] = industries

    geographies = icp.get("geographies")
    if geographies and isinstance(geographies, list):
        filters["geo_regions"] = geographies

    company_size = icp.get("company_size")
    if company_size:
        # company_size can be a dict {min, max} or a list of range labels
        if isinstance(company_size, list):
            filters["company_sizes"] = company_size
        elif isinstance(company_size, dict):
            # Build a descriptive label from min/max
            min_s = company_size.get("min")
            max_s = company_size.get("max")
            if min_s is not None or max_s is not None:
                label = "{}-{}".format(
                    min_s if min_s is not None else "1",
                    max_s if max_s is not None else "10000+",
                )
                filters["company_sizes"] = [label]

    # Collect seniority levels from personas
    personas = icp.get("personas", [])
    if not isinstance(personas, list):
        personas = []
    seniority_set = set()
    for persona in personas:
        if isinstance(persona, dict):
            seniority = persona.get("seniority")
            if seniority and isinstance(seniority, str):
                seniority_set.add(seniority)
            # Also check seniority_level as alternative field name
            seniority_level = persona.get("seniority_level")
            if seniority_level and isinstance(seniority_level, str):
                seniority_set.add(seniority_level)
    if seniority_set:
        filters["seniority_levels"] = sorted(seniority_set)

    return filters


def _count_matching_contacts(tenant_id: str, filters: dict) -> int:
    """Count contacts matching the given filter criteria."""
    params: dict = {"tenant_id": tenant_id}
    where = [
        "ct.tenant_id = :tenant_id",
        "(ct.is_disqualified = false OR ct.is_disqualified IS NULL)",
    ]

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

    where_clause = " AND ".join(where)

    total = (
        db.session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM contacts ct
                LEFT JOIN companies co ON ct.company_id = co.id
                WHERE {}
            """.format(where_clause)
            ),
            params,
        ).scalar()
        or 0
    )
    return total


def _build_top_segments(tenant_id: str, filters: dict) -> list[dict]:
    """Return top segments (industry + count) for the filtered contacts."""
    params: dict = {"tenant_id": tenant_id}
    where = [
        "ct.tenant_id = :tenant_id",
        "(ct.is_disqualified = false OR ct.is_disqualified IS NULL)",
    ]

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

    where_clause = " AND ".join(where)

    rows = db.session.execute(
        text(
            """
            SELECT co.industry, COUNT(*) AS cnt
            FROM contacts ct
            LEFT JOIN companies co ON ct.company_id = co.id
            WHERE {}
            GROUP BY co.industry
            ORDER BY cnt DESC
            LIMIT 5
        """.format(where_clause)
        ),
        params,
    ).fetchall()

    return [
        {"segment": r[0] or "Unknown", "count": r[1]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------


def apply_icp_filters(args: dict, ctx: ToolContext) -> dict:
    """Map ICP criteria from the strategy document to contact filters.

    Reads the tenant's StrategyDocument.extracted_data.icp, maps fields
    to contact filter parameters, counts matches, and returns a
    side_effect for the frontend ChatFilterSyncBar.
    """
    doc = StrategyDocument.query.filter_by(tenant_id=ctx.tenant_id).first()
    if not doc:
        return {"error": "No strategy document found."}

    extracted = _parse_jsonb(doc.extracted_data) if doc.extracted_data else None
    if not extracted or not isinstance(extracted, dict):
        return {
            "total_matches": 0,
            "filters_applied": {},
            "top_segments": [],
            "message": "No ICP data extracted yet. Run Extract ICP first.",
        }

    icp = extracted.get("icp", {})
    if not icp or not isinstance(icp, dict):
        return {
            "total_matches": 0,
            "filters_applied": {},
            "top_segments": [],
            "message": "No ICP data extracted yet. Run Extract ICP first.",
        }

    # Personas may be at top-level or inside icp — merge both
    top_personas = extracted.get("personas", [])
    icp_personas = icp.get("personas", [])
    if top_personas and not icp_personas:
        icp["personas"] = top_personas

    # Map ICP to filters
    filters = _map_icp_to_filters(icp)
    if not filters:
        return {
            "total_matches": 0,
            "filters_applied": {},
            "top_segments": [],
            "message": "ICP data found but no mappable filter criteria.",
        }

    # Count matches
    total_matches = _count_matching_contacts(ctx.tenant_id, filters)

    # Get top segments
    top_segments = _build_top_segments(ctx.tenant_id, filters)

    # Build human-readable description of applied filters
    desc_parts = []
    if "industries" in filters:
        desc_parts.append(
            "industries: {}".format(", ".join(filters["industries"]))
        )
    if "geo_regions" in filters:
        desc_parts.append(
            "regions: {}".format(", ".join(filters["geo_regions"]))
        )
    if "seniority_levels" in filters:
        desc_parts.append(
            "seniority: {}".format(", ".join(filters["seniority_levels"]))
        )
    if "company_sizes" in filters:
        desc_parts.append(
            "size: {}".format(", ".join(filters["company_sizes"]))
        )
    description = "ICP filters: " + "; ".join(desc_parts) if desc_parts else "ICP filters applied"

    return {
        "total_matches": total_matches,
        "filters_applied": filters,
        "top_segments": top_segments,
        "message": "Found {} contacts matching ICP criteria.".format(total_matches),
        "side_effect": {
            "type": "filter_sync",
            "payload": {
                "id": str(uuid.uuid4()),
                "description": description,
                "filters": filters,
            },
        },
    }


# ---------------------------------------------------------------------------
# Tool definitions for registry
# ---------------------------------------------------------------------------

ICP_FILTER_TOOLS = [
    ToolDefinition(
        name="apply_icp_filters",
        description=(
            "Map ICP criteria from the strategy document to contact filters. "
            "Reads the extracted ICP data (industries, geographies, company "
            "size, persona seniority levels) and translates them into contact "
            "filter parameters. Returns total matching contacts, the filters "
            "applied, and top segments by industry. Also emits a filter_sync "
            "side effect so the frontend can show a filter bar. Use this when "
            "the user wants to find contacts matching their ICP or when "
            "transitioning from strategy to contacts phase."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        handler=apply_icp_filters,
    ),
]

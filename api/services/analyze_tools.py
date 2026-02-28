"""Contacts & Companies analyzer tool handlers for AI chat tool-use.

Provides four tools that let the AI agent query the user's CRM data:
- count_contacts: Count contacts with optional filters
- count_companies: Count companies with optional filters
- list_contacts: List contacts with filters (paginated)
- list_companies: List companies with filters (paginated)

All queries are tenant-isolated and use parameterized SQL.
Registered with the AGENT tool registry at app startup.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from ..models import db
from .tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)

# Maximum items per page for list queries
MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_contact_filters(filters, params):
    """Build WHERE clauses for contact queries.

    Args:
        filters: dict of filter key/value pairs from the tool input.
        params: dict to populate with SQL bind parameters.

    Returns:
        list of SQL clause strings (already referencing :param names).
    """
    clauses = []

    company_name = filters.get("company_name")
    if company_name and isinstance(company_name, str):
        clauses.append("LOWER(co.name) LIKE LOWER(:company_name)")
        params["company_name"] = "%{}%".format(company_name)

    tag = filters.get("tag")
    if tag and isinstance(tag, str):
        clauses.append("LOWER(t.name) LIKE LOWER(:tag_name)")
        params["tag_name"] = "%{}%".format(tag)

    enrichment_status = filters.get("enrichment_status")
    if enrichment_status and isinstance(enrichment_status, str):
        clauses.append("ct.message_status = :enrichment_status")
        params["enrichment_status"] = enrichment_status

    has_email = filters.get("has_email")
    if has_email is True:
        clauses.append("ct.email_address IS NOT NULL AND ct.email_address != ''")
    elif has_email is False:
        clauses.append("(ct.email_address IS NULL OR ct.email_address = '')")

    return clauses


def _build_company_filters(filters, params):
    """Build WHERE clauses for company queries.

    Args:
        filters: dict of filter key/value pairs from the tool input.
        params: dict to populate with SQL bind parameters.

    Returns:
        list of SQL clause strings.
    """
    clauses = []

    status = filters.get("status")
    if status and isinstance(status, str):
        clauses.append("co.status = :status")
        params["status"] = status

    tag = filters.get("tag")
    if tag and isinstance(tag, str):
        clauses.append("LOWER(t.name) LIKE LOWER(:tag_name)")
        params["tag_name"] = "%{}%".format(tag)

    industry = filters.get("industry")
    if industry and isinstance(industry, str):
        clauses.append("LOWER(co.industry) LIKE LOWER(:industry)")
        params["industry"] = "%{}%".format(industry)

    tier = filters.get("tier")
    if tier and isinstance(tier, str):
        clauses.append("co.tier = :tier")
        params["tier"] = tier

    return clauses


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def count_contacts(args: dict, ctx: ToolContext) -> dict:
    """Count contacts with optional filters, tenant-isolated."""
    filters = args.get("filters") or {}
    if not isinstance(filters, dict):
        return {"error": "filters must be a JSON object"}

    params = {"tenant_id": ctx.tenant_id}
    where_clauses = _build_contact_filters(filters, params)

    # Always filter by tenant
    base_where = "ct.tenant_id = :tenant_id"
    if where_clauses:
        base_where += " AND " + " AND ".join(where_clauses)

    sql = """
        SELECT COUNT(DISTINCT ct.id) AS cnt
        FROM contacts ct
        LEFT JOIN companies co ON ct.company_id = co.id
        LEFT JOIN tags t ON ct.tag_id = t.id
        WHERE {where}
    """.format(where=base_where)

    result = db.session.execute(text(sql), params)
    row = result.fetchone()
    count = row[0] if row else 0

    return {
        "count": count,
        "filters_applied": {k: v for k, v in filters.items() if v is not None},
    }


def count_companies(args: dict, ctx: ToolContext) -> dict:
    """Count companies with optional filters, tenant-isolated."""
    filters = args.get("filters") or {}
    if not isinstance(filters, dict):
        return {"error": "filters must be a JSON object"}

    params = {"tenant_id": ctx.tenant_id}
    where_clauses = _build_company_filters(filters, params)

    base_where = "co.tenant_id = :tenant_id"
    if where_clauses:
        base_where += " AND " + " AND ".join(where_clauses)

    sql = """
        SELECT COUNT(DISTINCT co.id) AS cnt
        FROM companies co
        LEFT JOIN tags t ON co.tag_id = t.id
        WHERE {where}
    """.format(where=base_where)

    result = db.session.execute(text(sql), params)
    row = result.fetchone()
    count = row[0] if row else 0

    return {
        "count": count,
        "filters_applied": {k: v for k, v in filters.items() if v is not None},
    }


def list_contacts(args: dict, ctx: ToolContext) -> dict:
    """List contacts with filters, paginated, tenant-isolated."""
    filters = args.get("filters") or {}
    if not isinstance(filters, dict):
        return {"error": "filters must be a JSON object"}

    limit = min(int(args.get("limit", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
    offset = max(int(args.get("offset", 0)), 0)

    params = {"tenant_id": ctx.tenant_id, "limit": limit, "offset": offset}
    where_clauses = _build_contact_filters(filters, params)

    base_where = "ct.tenant_id = :tenant_id"
    if where_clauses:
        base_where += " AND " + " AND ".join(where_clauses)

    # Count total
    count_sql = """
        SELECT COUNT(DISTINCT ct.id) AS cnt
        FROM contacts ct
        LEFT JOIN companies co ON ct.company_id = co.id
        LEFT JOIN tags t ON ct.tag_id = t.id
        WHERE {where}
    """.format(where=base_where)
    total = db.session.execute(text(count_sql), params).fetchone()[0]

    # Fetch page
    data_sql = """
        SELECT ct.first_name, ct.last_name, ct.email_address,
               co.name AS company_name,
               t.name AS tag_name,
               ct.message_status
        FROM contacts ct
        LEFT JOIN companies co ON ct.company_id = co.id
        LEFT JOIN tags t ON ct.tag_id = t.id
        WHERE {where}
        ORDER BY ct.created_at DESC
        LIMIT :limit OFFSET :offset
    """.format(where=base_where)

    rows = db.session.execute(text(data_sql), params).fetchall()

    contacts = []
    for row in rows:
        name_parts = [row[0] or ""]
        if row[1]:
            name_parts.append(row[1])
        contacts.append(
            {
                "name": " ".join(name_parts).strip(),
                "email": row[2] or None,
                "company_name": row[3] or None,
                "tags": [row[4]] if row[4] else [],
                "enrichment_status": row[5] or None,
            }
        )

    return {
        "contacts": contacts,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def list_companies(args: dict, ctx: ToolContext) -> dict:
    """List companies with filters, paginated, tenant-isolated."""
    filters = args.get("filters") or {}
    if not isinstance(filters, dict):
        return {"error": "filters must be a JSON object"}

    limit = min(int(args.get("limit", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
    offset = max(int(args.get("offset", 0)), 0)

    params = {"tenant_id": ctx.tenant_id, "limit": limit, "offset": offset}
    where_clauses = _build_company_filters(filters, params)

    base_where = "co.tenant_id = :tenant_id"
    if where_clauses:
        base_where += " AND " + " AND ".join(where_clauses)

    # Count total
    count_sql = """
        SELECT COUNT(DISTINCT co.id) AS cnt
        FROM companies co
        LEFT JOIN tags t ON co.tag_id = t.id
        WHERE {where}
    """.format(where=base_where)
    total = db.session.execute(text(count_sql), params).fetchone()[0]

    # Fetch page with contact count subquery
    data_sql = """
        SELECT co.name, co.status, co.tier, co.industry,
               t.name AS tag_name,
               (SELECT COUNT(*) FROM contacts c2
                WHERE c2.company_id = co.id
                  AND c2.tenant_id = :tenant_id) AS contact_count
        FROM companies co
        LEFT JOIN tags t ON co.tag_id = t.id
        WHERE {where}
        ORDER BY co.created_at DESC
        LIMIT :limit OFFSET :offset
    """.format(where=base_where)

    rows = db.session.execute(text(data_sql), params).fetchall()

    companies = []
    for row in rows:
        companies.append(
            {
                "name": row[0] or "",
                "status": row[1] or None,
                "tier": row[2] or None,
                "industry": row[3] or None,
                "tags": [row[4]] if row[4] else [],
                "contact_count": row[5] or 0,
            }
        )

    return {
        "companies": companies,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# Tool definitions for registry
# ---------------------------------------------------------------------------

ANALYZE_TOOLS = [
    ToolDefinition(
        name="count_contacts",
        description=(
            "Count contacts in the CRM with optional filters. "
            "Use this to answer questions like 'how many contacts do we have?' "
            "or 'how many contacts at tech companies have emails?'"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "description": (
                        "Optional filters to narrow the count. All filters are AND-combined."
                    ),
                    "properties": {
                        "company_name": {
                            "type": "string",
                            "description": "Partial match on the associated company name.",
                        },
                        "tag": {
                            "type": "string",
                            "description": "Partial match on the contact's tag/batch name.",
                        },
                        "enrichment_status": {
                            "type": "string",
                            "description": (
                                "Exact match on message_status. Values: "
                                "not_started, pending_review, approved, sent, generating."
                            ),
                        },
                        "has_email": {
                            "type": "boolean",
                            "description": "True = only contacts with email, False = only without.",
                        },
                    },
                },
            },
            "required": [],
        },
        handler=count_contacts,
    ),
    ToolDefinition(
        name="count_companies",
        description=(
            "Count companies in the CRM with optional filters. "
            "Use this for questions like 'how many companies are enriched?' "
            "or 'how many companies in manufacturing?'"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "description": "Optional filters to narrow the count.",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": (
                                "Exact match on company status. Values: "
                                "new, triage_passed, triage_disqualified, "
                                "enriched_l2, enrichment_l2_failed."
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "description": "Partial match on the company's tag/batch name.",
                        },
                        "industry": {
                            "type": "string",
                            "description": "Partial match on industry field.",
                        },
                        "tier": {
                            "type": "string",
                            "description": (
                                "Exact match on tier. Values: "
                                "tier_1_platinum, tier_2_gold, tier_3_silver, "
                                "tier_4_bronze, tier_5_copper."
                            ),
                        },
                    },
                },
            },
            "required": [],
        },
        handler=count_companies,
    ),
    ToolDefinition(
        name="list_contacts",
        description=(
            "List contacts with optional filters and pagination. "
            "Returns name, email, company, tags, and enrichment status. "
            "Use for browsing contacts or finding specific people."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "description": "Same filter options as count_contacts.",
                    "properties": {
                        "company_name": {
                            "type": "string",
                            "description": "Partial match on company name.",
                        },
                        "tag": {
                            "type": "string",
                            "description": "Partial match on tag/batch name.",
                        },
                        "enrichment_status": {
                            "type": "string",
                            "description": "Exact match on message_status.",
                        },
                        "has_email": {
                            "type": "boolean",
                            "description": "Filter by email presence.",
                        },
                    },
                },
                "limit": {
                    "type": "integer",
                    "description": "Max contacts to return (default 10, max 50).",
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of contacts to skip (for pagination).",
                },
            },
            "required": [],
        },
        handler=list_contacts,
    ),
    ToolDefinition(
        name="list_companies",
        description=(
            "List companies with optional filters and pagination. "
            "Returns name, status, tier, industry, tags, and contact count. "
            "Use for browsing companies or analyzing the pipeline."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "description": "Same filter options as count_companies.",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Exact match on company status.",
                        },
                        "tag": {
                            "type": "string",
                            "description": "Partial match on tag/batch name.",
                        },
                        "industry": {
                            "type": "string",
                            "description": "Partial match on industry.",
                        },
                        "tier": {
                            "type": "string",
                            "description": "Exact match on tier.",
                        },
                    },
                },
                "limit": {
                    "type": "integer",
                    "description": "Max companies to return (default 10, max 50).",
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of companies to skip (for pagination).",
                },
            },
            "required": [],
        },
        handler=list_companies,
    ),
]

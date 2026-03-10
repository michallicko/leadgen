"""Read-only tools for the Copilot agent.

Provides quick data lookups without modifying any state. All queries
filter by tenant_id for multi-tenant safety.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Tool names available to the copilot agent
COPILOT_TOOL_NAMES = frozenset(
    [
        "get_contact_info",
        "get_company_info",
        "get_pipeline_status",
        "get_recent_activity",
    ]
)


def get_contact_info(args: dict, context: Any) -> dict:
    """Look up contact information by name or ID.

    Args:
        args: {"query": "search string or contact ID"}
        context: ToolContext with tenant_id.

    Returns:
        Contact summary dict or error.
    """
    from ..models import Contact, db

    tenant_id = context.tenant_id
    query = args.get("query", "").strip()

    if not query:
        return {"error": "query is required"}

    # Try UUID lookup first
    try:
        import uuid

        uuid.UUID(query)
        contact = Contact.query.filter_by(id=query, tenant_id=tenant_id).first()
        if contact:
            return _contact_to_dict(contact)
    except (ValueError, AttributeError):
        pass

    # Name search (case-insensitive)
    contacts = (
        Contact.query.filter(
            Contact.tenant_id == tenant_id,
            db.or_(
                Contact.first_name.ilike("%{}%".format(query)),
                Contact.last_name.ilike("%{}%".format(query)),
                Contact.email.ilike("%{}%".format(query)),
            ),
        )
        .limit(5)
        .all()
    )

    if not contacts:
        return {
            "results": [],
            "message": "No contacts found matching '{}'".format(query),
        }

    return {
        "results": [_contact_to_dict(c) for c in contacts],
        "count": len(contacts),
    }


def get_company_info(args: dict, context: Any) -> dict:
    """Look up company information by name or ID.

    Args:
        args: {"query": "search string or company ID"}
        context: ToolContext with tenant_id.

    Returns:
        Company summary dict or error.
    """
    from ..models import Company

    tenant_id = context.tenant_id
    query = args.get("query", "").strip()

    if not query:
        return {"error": "query is required"}

    # Try UUID lookup first
    try:
        import uuid

        uuid.UUID(query)
        company = Company.query.filter_by(id=query, tenant_id=tenant_id).first()
        if company:
            return _company_to_dict(company)
    except (ValueError, AttributeError):
        pass

    # Name search
    companies = (
        Company.query.filter(
            Company.tenant_id == tenant_id,
            Company.name.ilike("%{}%".format(query)),
        )
        .limit(5)
        .all()
    )

    if not companies:
        return {
            "results": [],
            "message": "No companies found matching '{}'".format(query),
        }

    return {
        "results": [_company_to_dict(c) for c in companies],
        "count": len(companies),
    }


def get_pipeline_status(args: dict, context: Any) -> dict:
    """Get current pipeline phase and status summary.

    Returns counts of contacts/companies at each stage.
    """
    from ..models import Company, Contact, db

    tenant_id = context.tenant_id

    # Company status counts
    company_counts = (
        db.session.query(Company.status, db.func.count(Company.id))
        .filter(Company.tenant_id == tenant_id)
        .group_by(Company.status)
        .all()
    )

    # Contact counts
    total_contacts = Contact.query.filter_by(tenant_id=tenant_id).count()

    return {
        "company_status_counts": {
            status: count for status, count in company_counts if status
        },
        "total_contacts": total_contacts,
        "summary": "Pipeline status retrieved",
    }


def get_recent_activity(args: dict, context: Any) -> dict:
    """Get recent operations/events for the tenant.

    Args:
        args: {"limit": N} — defaults to 10.

    Returns:
        List of recent activity entries.
    """
    from ..models import LLMUsage

    tenant_id = context.tenant_id
    limit = min(args.get("limit", 10), 25)

    # Get recent LLM usage as a proxy for activity
    recent = (
        LLMUsage.query.filter_by(tenant_id=tenant_id)
        .order_by(LLMUsage.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "activities": [
            {
                "id": str(r.id),
                "operation": r.operation or "chat",
                "model": r.model,
                "tokens": (r.input_tokens or 0) + (r.output_tokens or 0),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recent
        ],
        "count": len(recent),
    }


# Tool definitions for registration
COPILOT_TOOL_DEFINITIONS = [
    {
        "name": "get_contact_info",
        "description": "Look up contact information by name, email, or ID. Returns matching contacts with key details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Contact name, email, or UUID to search for",
                }
            },
            "required": ["query"],
        },
        "handler": get_contact_info,
    },
    {
        "name": "get_company_info",
        "description": "Look up company information by name or ID. Returns matching companies with status and details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Company name or UUID to search for",
                }
            },
            "required": ["query"],
        },
        "handler": get_company_info,
    },
    {
        "name": "get_pipeline_status",
        "description": "Get current pipeline status showing company counts by stage and total contacts.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
        "handler": get_pipeline_status,
    },
    {
        "name": "get_recent_activity",
        "description": "Get recent operations and events for the current tenant.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of recent activities to return (max 25)",
                    "default": 10,
                }
            },
        },
        "handler": get_recent_activity,
    },
]


def _contact_to_dict(contact) -> dict:
    """Convert a Contact model to a summary dict."""
    return {
        "id": str(contact.id),
        "first_name": contact.first_name or "",
        "last_name": contact.last_name or "",
        "email": contact.email or "",
        "title": contact.title or "",
        "company_id": str(contact.company_id) if contact.company_id else None,
    }


def _company_to_dict(company) -> dict:
    """Convert a Company model to a summary dict."""
    return {
        "id": str(company.id),
        "name": company.name or "",
        "status": company.status or "",
        "domain": company.domain or "",
        "industry": company.industry or "",
    }

"""Campaign management tool handlers for AI chat tool-use.

Provides five tools that let the AI agent manage campaigns and contacts:
- filter_contacts: Search and filter the user's contact pool
- create_campaign: Create a new outreach campaign
- assign_to_campaign: Add contacts to an existing campaign
- check_strategy_conflicts: Check for strategy conflicts
- get_campaign_summary: Get campaign stats and contact breakdown

All queries are tenant-isolated and use parameterized SQL.
Registered with the AGENT tool registry at app startup.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text

from ..models import Campaign, CampaignContact, CampaignOverlapLog, db
from .tool_registry import ToolContext, ToolDefinition

logger = logging.getLogger(__name__)

MAX_CONTACTS_RETURNED = 50
DEFAULT_CONTACTS_RETURNED = 10


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
# Tool handlers
# ---------------------------------------------------------------------------


def filter_contacts(args: dict, ctx: ToolContext) -> dict:
    """Search and filter the user's contact pool. Returns matching contacts."""
    limit = min(int(args.get("limit", DEFAULT_CONTACTS_RETURNED)), MAX_CONTACTS_RETURNED)
    params = {"tenant_id": ctx.tenant_id, "limit": limit}
    where = [
        "ct.tenant_id = :tenant_id",
        "(ct.is_disqualified = false OR ct.is_disqualified IS NULL)",
    ]

    # Multi-value filters
    multi = {
        "tiers": ("co.tier", "tier"),
        "industries": ("co.industry", "ind"),
        "seniority_levels": ("ct.seniority_level", "sen"),
        "departments": ("ct.department", "dept"),
        "geo_regions": ("co.geo_region", "geo"),
        "company_sizes": ("co.company_size", "csz"),
    }
    for key, (column, prefix) in multi.items():
        values = args.get(key, [])
        if not values or not isinstance(values, list):
            continue
        phs = []
        for i, v in enumerate(values):
            pname = "{}_{}".format(prefix, i)
            params[pname] = v
            phs.append(":{}".format(pname))
        where.append("{} IN ({})".format(column, ", ".join(phs)))

    # Score filter
    min_score = args.get("min_contact_score")
    if min_score is not None:
        where.append("ct.contact_score >= :min_score")
        params["min_score"] = int(min_score)

    # Text search
    search = (args.get("search") or "").strip()
    if search:
        where.append(
            "(LOWER(ct.first_name || ' ' || COALESCE(ct.last_name, '')) "
            "LIKE LOWER(:search) "
            "OR LOWER(co.name) LIKE LOWER(:search))"
        )
        params["search"] = "%{}%".format(search)

    # Enrichment readiness
    if args.get("enrichment_ready"):
        where.append("""EXISTS (
            SELECT 1 FROM entity_stage_completions esc
            WHERE esc.entity_id = co.id AND esc.tenant_id = :tenant_id
                AND esc.stage = 'l1_company' AND esc.status = 'completed'
        )""")
        where.append("""EXISTS (
            SELECT 1 FROM entity_stage_completions esc
            WHERE esc.entity_id = co.id AND esc.tenant_id = :tenant_id
                AND esc.stage = 'l2_deep_research' AND esc.status = 'completed'
        )""")
        where.append("""EXISTS (
            SELECT 1 FROM entity_stage_completions esc
            WHERE esc.entity_id = ct.id AND esc.tenant_id = :tenant_id
                AND esc.stage = 'person' AND esc.status = 'completed'
        )""")

    # Exclude contacts in active campaigns
    if args.get("exclude_in_campaigns"):
        where.append("""NOT EXISTS (
            SELECT 1 FROM campaign_contacts cc
            JOIN campaigns c ON c.id = cc.campaign_id
            WHERE cc.contact_id = ct.id AND c.is_active = true
                AND c.status IN ('draft', 'ready', 'approved', 'sending')
        )""")

    where_clause = " AND ".join(where)

    # Count total matches
    total = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM contacts ct
            LEFT JOIN companies co ON ct.company_id = co.id
            WHERE {}
        """.format(where_clause)),
        params,
    ).scalar() or 0

    # Fetch top contacts
    data_params = dict(params)
    rows = db.session.execute(
        text("""
            SELECT ct.id, ct.first_name, ct.last_name, ct.job_title,
                   ct.email_address, ct.linkedin_url, ct.seniority_level,
                   ct.contact_score, ct.icp_fit,
                   co.name AS company_name, co.tier, co.industry
            FROM contacts ct
            LEFT JOIN companies co ON ct.company_id = co.id
            WHERE {}
            ORDER BY ct.contact_score DESC NULLS LAST
            LIMIT :limit
        """.format(where_clause)),
        data_params,
    ).fetchall()

    contacts = []
    for r in rows:
        full_name = ((r[1] or "") + " " + (r[2] or "")).strip()
        contacts.append({
            "id": str(r[0]),
            "full_name": full_name,
            "job_title": r[3],
            "email": r[4],
            "linkedin_url": r[5],
            "seniority": r[6],
            "contact_score": r[7],
            "icp_fit": r[8],
            "company_name": r[9],
            "tier": r[10],
            "industry": r[11],
        })

    return {
        "total": total,
        "returned": len(contacts),
        "contacts": contacts,
        "filters_applied": {
            k: v for k, v in args.items()
            if v is not None and k != "limit" and v != [] and v != ""
        },
    }


def create_campaign(args: dict, ctx: ToolContext) -> dict:
    """Create a new outreach campaign."""
    name = (args.get("name") or "").strip()
    if not name:
        return {"error": "Campaign name is required."}

    # Check for duplicate name among active campaigns
    existing = db.session.execute(
        text("""
            SELECT id, status FROM campaigns
            WHERE tenant_id = :t AND name = :name AND is_active = true
        """),
        {"t": ctx.tenant_id, "name": name},
    ).fetchone()
    if existing:
        return {
            "error": "A campaign named '{}' already exists (status: {}). "
            "Choose a different name or add contacts to the existing campaign.".format(
                name, existing[1]
            ),
            "existing_campaign_id": str(existing[0]),
        }

    description = args.get("description", "")
    strategy_id = args.get("strategy_id")
    target_criteria = args.get("target_criteria", {})

    campaign = Campaign(
        tenant_id=ctx.tenant_id,
        name=name,
        description=description,
        status="draft",
        strategy_id=strategy_id,
        target_criteria=json.dumps(target_criteria)
        if isinstance(target_criteria, dict) else target_criteria,
    )
    db.session.add(campaign)
    db.session.commit()

    return {
        "campaign_id": str(campaign.id),
        "name": name,
        "status": "draft",
        "message": "Campaign '{}' created successfully.".format(name),
    }


def assign_to_campaign(args: dict, ctx: ToolContext) -> dict:
    """Add contacts to an existing campaign with overlap detection."""
    campaign_id = args.get("campaign_id")
    if not campaign_id:
        return {"error": "campaign_id is required."}

    # Verify campaign
    campaign = db.session.execute(
        text("""
            SELECT id, name, status FROM campaigns
            WHERE id = :id AND tenant_id = :t
        """),
        {"id": campaign_id, "t": ctx.tenant_id},
    ).fetchone()
    if not campaign:
        return {"error": "Campaign not found."}
    if campaign[2] not in ("draft", "ready"):
        return {"error": "Can only add contacts to draft or ready campaigns."}

    # Resolve contact IDs from various sources
    contact_ids = list(args.get("contact_ids", []))

    # From company_ids
    company_ids = args.get("company_ids", [])
    if company_ids:
        comp_phs = []
        comp_params = {"t": ctx.tenant_id}
        for i, v in enumerate(company_ids):
            pname = "comp_{}".format(i)
            comp_params[pname] = v
            comp_phs.append(":{}".format(pname))
        company_contacts = db.session.execute(
            text("""
                SELECT id FROM contacts
                WHERE tenant_id = :t AND company_id IN ({})
                    AND (is_disqualified = false OR is_disqualified IS NULL)
            """.format(", ".join(comp_phs))),
            comp_params,
        ).fetchall()
        contact_ids.extend(str(r[0]) for r in company_contacts)

    # From filters
    filters = args.get("filters")
    if filters and isinstance(filters, dict):
        # Reuse filter_contacts logic to resolve IDs
        filter_result = filter_contacts(
            {**filters, "limit": 1000}, ctx
        )
        if "contacts" in filter_result:
            contact_ids.extend(c["id"] for c in filter_result["contacts"])

    contact_ids = list(set(contact_ids))
    if not contact_ids:
        return {"error": "No contacts found for given criteria."}

    # Validate contacts belong to tenant
    id_phs = []
    id_params = {"t": ctx.tenant_id}
    for i, v in enumerate(contact_ids):
        pname = "id_{}".format(i)
        id_params[pname] = v
        id_phs.append(":{}".format(pname))
    valid = db.session.execute(
        text("""
            SELECT id FROM contacts
            WHERE tenant_id = :t AND id IN ({})
                AND (is_disqualified = false OR is_disqualified IS NULL)
        """.format(", ".join(id_phs))),
        id_params,
    ).fetchall()
    valid_ids = {str(r[0]) for r in valid}

    # Get existing assignments
    existing = db.session.execute(
        text("""
            SELECT contact_id FROM campaign_contacts
            WHERE campaign_id = :cid AND tenant_id = :t
        """),
        {"cid": campaign_id, "t": ctx.tenant_id},
    ).fetchall()
    existing_ids = {str(r[0]) for r in existing}

    # Check for overlaps with other active campaigns
    overlap_warnings = []
    new_ids = [cid for cid in contact_ids if cid in valid_ids and cid not in existing_ids]
    if new_ids:
        ovl_phs = []
        ovl_params = {"t": ctx.tenant_id, "cid": campaign_id}
        for i, v in enumerate(new_ids):
            pname = "ovl_{}".format(i)
            ovl_params[pname] = v
            ovl_phs.append(":{}".format(pname))
        ovl_rows = db.session.execute(
            text("""
                SELECT cc.contact_id, c.name, c.status
                FROM campaign_contacts cc
                JOIN campaigns c ON c.id = cc.campaign_id
                WHERE cc.tenant_id = :t
                    AND cc.contact_id IN ({})
                    AND cc.campaign_id != :cid
                    AND c.is_active = true
                    AND c.status IN ('draft', 'ready', 'approved', 'sending')
            """.format(", ".join(ovl_phs))),
            ovl_params,
        ).fetchall()
        for r in ovl_rows:
            overlap_warnings.append({
                "contact_id": str(r[0]),
                "campaign_name": r[1],
                "campaign_status": r[2],
            })
            # Log overlap
            log = CampaignOverlapLog(
                tenant_id=ctx.tenant_id,
                contact_id=str(r[0]),
                campaign_id=campaign_id,
                overlapping_campaign_id=str(r[0]),
                overlap_type="active_campaign",
            )
            db.session.add(log)

    # Add contacts
    added = 0
    skipped = 0
    for cid in contact_ids:
        if cid not in valid_ids:
            continue
        if cid in existing_ids:
            skipped += 1
            continue
        cc = CampaignContact(
            campaign_id=campaign_id,
            contact_id=cid,
            tenant_id=ctx.tenant_id,
            status="pending",
        )
        db.session.add(cc)
        added += 1

    if added > 0:
        db.session.flush()
        db.session.execute(
            text("""
                UPDATE campaigns
                SET total_contacts = (
                    SELECT COUNT(*) FROM campaign_contacts WHERE campaign_id = :cid
                )
                WHERE id = :cid
            """),
            {"cid": campaign_id},
        )

    db.session.commit()

    return {
        "added": added,
        "skipped": skipped,
        "total": added + len(existing_ids),
        "overlap_warnings": overlap_warnings,
        "message": "Added {} contacts to '{}'. {} skipped (already assigned).".format(
            added, campaign[1], skipped
        ),
    }


def check_strategy_conflicts(args: dict, ctx: ToolContext) -> dict:
    """Check for strategy conflicts when adding contacts to a campaign."""
    campaign_id = args.get("campaign_id")
    if not campaign_id:
        return {"error": "campaign_id is required."}

    campaign = db.session.execute(
        text("""
            SELECT id, strategy_id, contact_cooldown_days, channel,
                   generation_config
            FROM campaigns WHERE id = :id AND tenant_id = :t
        """),
        {"id": campaign_id, "t": ctx.tenant_id},
    ).fetchone()
    if not campaign:
        return {"error": "Campaign not found."}

    strategy_id = args.get("strategy_id") or (
        str(campaign[1]) if campaign[1] else None
    )
    contact_ids = args.get("contact_ids", [])

    # Load contacts
    if contact_ids:
        cid_phs = []
        cid_params = {"t": ctx.tenant_id}
        for i, v in enumerate(contact_ids):
            pname = "cid_{}".format(i)
            cid_params[pname] = v
            cid_phs.append(":{}".format(pname))
        contacts = db.session.execute(
            text("""
                SELECT ct.id, ct.first_name, ct.last_name,
                       ct.email_address, ct.linkedin_url,
                       ct.relationship_status,
                       co.industry, co.geo_region, co.verified_employees
                FROM contacts ct
                LEFT JOIN companies co ON ct.company_id = co.id
                WHERE ct.tenant_id = :t AND ct.id IN ({})
            """.format(", ".join(cid_phs))),
            cid_params,
        ).fetchall()
    else:
        contacts = db.session.execute(
            text("""
                SELECT ct.id, ct.first_name, ct.last_name,
                       ct.email_address, ct.linkedin_url,
                       ct.relationship_status,
                       co.industry, co.geo_region, co.verified_employees
                FROM campaign_contacts cc
                JOIN contacts ct ON cc.contact_id = ct.id
                LEFT JOIN companies co ON ct.company_id = co.id
                WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            """),
            {"cid": campaign_id, "t": ctx.tenant_id},
        ).fetchall()

    if not contacts:
        return {
            "total_contacts": 0,
            "clean": 0,
            "with_warnings": 0,
            "with_errors": 0,
            "conflicts": [],
            "message": "No contacts to check.",
        }

    all_contact_ids = [str(r[0]) for r in contacts]

    # Load ICP
    icp = {}
    if strategy_id:
        strat = db.session.execute(
            text("""
                SELECT extracted_data FROM strategy_documents
                WHERE id = :id AND tenant_id = :t
            """),
            {"id": strategy_id, "t": ctx.tenant_id},
        ).fetchone()
        if strat and strat[0]:
            extracted = _parse_jsonb(strat[0]) if isinstance(strat[0], str) else strat[0]
            icp = (extracted or {}).get("icp", {})

    # Overlaps
    if all_contact_ids:
        ovl_phs = []
        ovl_params = {"t": ctx.tenant_id, "cid": campaign_id}
        for i, v in enumerate(all_contact_ids):
            pname = "oid_{}".format(i)
            ovl_params[pname] = v
            ovl_phs.append(":{}".format(pname))
        ovl_rows = db.session.execute(
            text("""
                SELECT cc.contact_id, c.name, c.status
                FROM campaign_contacts cc
                JOIN campaigns c ON c.id = cc.campaign_id
                WHERE cc.tenant_id = :t
                    AND cc.contact_id IN ({})
                    AND cc.campaign_id != :cid
                    AND c.is_active = true
            """.format(", ".join(ovl_phs))),
            ovl_params,
        ).fetchall()
    else:
        ovl_rows = []
    overlap_map = {}
    for r in ovl_rows:
        overlap_map.setdefault(str(r[0]), []).append({
            "campaign": r[1],
            "status": r[2],
        })

    # Build conflicts list
    conflicts = []
    contacts_with_warnings = set()
    contacts_with_errors = set()

    gen_config = _parse_jsonb(campaign[4]) if campaign[4] else {}
    campaign_tone = gen_config.get("tone") if isinstance(gen_config, dict) else None

    for row in contacts:
        cid = str(row[0])
        full_name = ((row[1] or "") + " " + (row[2] or "")).strip()
        email = row[3]
        linkedin = row[4]
        relationship = row[5]
        industry = row[6]
        geo_region = row[7]
        verified_employees = row[8]

        # ICP checks
        if icp:
            icp_industries = icp.get("industries", [])
            if icp_industries and industry and industry not in icp_industries:
                conflicts.append({
                    "type": "icp_mismatch",
                    "contact_id": cid,
                    "contact_name": full_name,
                    "detail": "Industry '{}' not in ICP".format(industry),
                    "severity": "warning",
                })
                contacts_with_warnings.add(cid)

            icp_geos = icp.get("geographies", [])
            if icp_geos and geo_region and geo_region not in icp_geos:
                conflicts.append({
                    "type": "icp_mismatch",
                    "contact_id": cid,
                    "contact_name": full_name,
                    "detail": "Region '{}' not in ICP".format(geo_region),
                    "severity": "warning",
                })
                contacts_with_warnings.add(cid)

            icp_size = icp.get("company_size", {})
            if icp_size and verified_employees:
                min_s = icp_size.get("min", 0)
                max_s = icp_size.get("max", 999999)
                emp = float(verified_employees)
                if emp < min_s or emp > max_s:
                    conflicts.append({
                        "type": "icp_mismatch",
                        "contact_id": cid,
                        "contact_name": full_name,
                        "detail": "{} employees (ICP: {}-{})".format(
                            int(emp), min_s, max_s
                        ),
                        "severity": "warning",
                    })
                    contacts_with_warnings.add(cid)

        # Channel gaps
        campaign_channel = campaign[3]
        if campaign_channel:
            if "email" in campaign_channel.lower() and not email:
                conflicts.append({
                    "type": "channel_gap",
                    "contact_id": cid,
                    "contact_name": full_name,
                    "detail": "No email address for email campaign",
                    "severity": "error",
                })
                contacts_with_errors.add(cid)
            if "linkedin" in campaign_channel.lower() and not linkedin:
                conflicts.append({
                    "type": "channel_gap",
                    "contact_id": cid,
                    "contact_name": full_name,
                    "detail": "No LinkedIn URL for LinkedIn campaign",
                    "severity": "error",
                })
                contacts_with_errors.add(cid)

        # Overlap
        if cid in overlap_map:
            for ovl in overlap_map[cid]:
                conflicts.append({
                    "type": "segment_overlap",
                    "contact_id": cid,
                    "contact_name": full_name,
                    "detail": "Also in '{}' ({})".format(ovl["campaign"], ovl["status"]),
                    "severity": "warning",
                })
                contacts_with_warnings.add(cid)

        # Tone mismatch
        if campaign_tone and relationship:
            if "cold" in campaign_tone and relationship in ("warm", "hot", "customer"):
                conflicts.append({
                    "type": "tone_mismatch",
                    "contact_id": cid,
                    "contact_name": full_name,
                    "detail": "Campaign tone '{}' but relationship is '{}'".format(
                        campaign_tone, relationship
                    ),
                    "severity": "warning",
                })
                contacts_with_warnings.add(cid)

    total = len(contacts)
    with_errors = len(contacts_with_errors)
    with_warnings = len(contacts_with_warnings - contacts_with_errors)
    clean = total - len(contacts_with_warnings | contacts_with_errors)

    # Build summary message
    if not conflicts:
        msg = "No strategy conflicts detected. All {} contacts are clean.".format(total)
    else:
        msg = "{} contacts checked: {} clean, {} with warnings, {} with errors.".format(
            total, clean, with_warnings, with_errors
        )

    return {
        "total_contacts": total,
        "clean": clean,
        "with_warnings": with_warnings,
        "with_errors": with_errors,
        "conflicts": conflicts,
        "message": msg,
    }


def get_campaign_summary(args: dict, ctx: ToolContext) -> dict:
    """Get campaign stats and contact breakdown."""
    campaign_id = args.get("campaign_id")
    if not campaign_id:
        return {"error": "campaign_id is required."}

    campaign = db.session.execute(
        text("""
            SELECT id, name, status, description, total_contacts,
                   generated_count, channel, created_at
            FROM campaigns WHERE id = :id AND tenant_id = :t
        """),
        {"id": campaign_id, "t": ctx.tenant_id},
    ).fetchone()
    if not campaign:
        return {"error": "Campaign not found."}

    # Contact breakdown by status
    status_rows = db.session.execute(
        text("""
            SELECT cc.status, COUNT(*)
            FROM campaign_contacts cc
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            GROUP BY cc.status
        """),
        {"cid": campaign_id, "t": ctx.tenant_id},
    ).fetchall()
    by_status = {r[0]: r[1] for r in status_rows}

    # Enrichment readiness
    ready_count = db.session.execute(
        text("""
            SELECT COUNT(DISTINCT ct.id)
            FROM campaign_contacts cc
            JOIN contacts ct ON cc.contact_id = ct.id
            LEFT JOIN companies co ON ct.company_id = co.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
                AND EXISTS (
                    SELECT 1 FROM entity_stage_completions e
                    WHERE e.entity_id = co.id AND e.tenant_id = :t
                        AND e.stage = 'l1_company' AND e.status = 'completed'
                )
                AND EXISTS (
                    SELECT 1 FROM entity_stage_completions e
                    WHERE e.entity_id = co.id AND e.tenant_id = :t
                        AND e.stage = 'l2_deep_research' AND e.status = 'completed'
                )
                AND EXISTS (
                    SELECT 1 FROM entity_stage_completions e
                    WHERE e.entity_id = ct.id AND e.tenant_id = :t
                        AND e.stage = 'person' AND e.status = 'completed'
                )
        """),
        {"cid": campaign_id, "t": ctx.tenant_id},
    ).scalar() or 0

    total_contacts = sum(by_status.values())

    return {
        "campaign_id": str(campaign[0]),
        "name": campaign[1],
        "status": campaign[2],
        "description": campaign[3],
        "total_contacts": total_contacts,
        "generated_count": campaign[5] or 0,
        "channel": campaign[6],
        "contacts_by_status": by_status,
        "enrichment_ready": ready_count,
        "enrichment_needed": total_contacts - ready_count,
        "created_at": (
            campaign[7].isoformat()
            if hasattr(campaign[7], "isoformat")
            else campaign[7]
        ) if campaign[7] else None,
    }


# ---------------------------------------------------------------------------
# Tool definitions for registry
# ---------------------------------------------------------------------------

CAMPAIGN_TOOLS = [
    ToolDefinition(
        name="filter_contacts",
        description=(
            "Search and filter the user's contact pool. Returns matching "
            "contacts with summary stats. Use this when the user wants to "
            "find contacts by criteria like industry, seniority, tier, "
            "region, etc."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tiers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Company tier filter (e.g., 'Tier 1 - Platinum')",
                },
                "industries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Company industry filter",
                },
                "seniority_levels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Contact seniority (C-Level, VP, Director, "
                        "Manager, Individual Contributor)"
                    ),
                },
                "departments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Contact department filter",
                },
                "geo_regions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Company geographic region",
                },
                "company_sizes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Company size range",
                },
                "min_contact_score": {
                    "type": "integer",
                    "description": "Minimum contact score (0-100)",
                },
                "enrichment_ready": {
                    "type": "boolean",
                    "description": "Only contacts with full enrichment (L1+L2+Person)",
                },
                "search": {
                    "type": "string",
                    "description": "Free text search across contact and company names",
                },
                "exclude_in_campaigns": {
                    "type": "boolean",
                    "description": "Exclude contacts already in active campaigns",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max contacts to return (default 10, max 50)",
                },
            },
        },
        handler=filter_contacts,
    ),
    ToolDefinition(
        name="create_campaign",
        description=(
            "Create a new outreach campaign. Returns the campaign ID. "
            "Use this when the user wants to start a new campaign."
        ),
        input_schema={
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Campaign name (must be unique within tenant)",
                },
                "description": {
                    "type": "string",
                    "description": "Campaign description/objective",
                },
                "strategy_id": {
                    "type": "string",
                    "description": "Link to a strategy document",
                },
                "target_criteria": {
                    "type": "object",
                    "description": (
                        "Filter criteria used to build the contact list "
                        "(for audit trail)"
                    ),
                },
            },
        },
        handler=create_campaign,
    ),
    ToolDefinition(
        name="assign_to_campaign",
        description=(
            "Add contacts to an existing campaign. Handles deduplication "
            "and detects overlaps with other active campaigns. Returns "
            "count of added/skipped contacts and overlap warnings."
        ),
        input_schema={
            "type": "object",
            "required": ["campaign_id"],
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Target campaign UUID",
                },
                "contact_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific contact UUIDs to add",
                },
                "company_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Add all contacts from these companies",
                },
                "filters": {
                    "type": "object",
                    "description": (
                        "Same filter object as filter_contacts -- "
                        "resolves to contact IDs"
                    ),
                },
            },
        },
        handler=assign_to_campaign,
    ),
    ToolDefinition(
        name="check_strategy_conflicts",
        description=(
            "Check for strategy conflicts when adding contacts to a "
            "campaign. Flags ICP mismatches, channel gaps, segment "
            "overlaps, and tone mismatches. Always call this before "
            "finalizing a campaign's contact list."
        ),
        input_schema={
            "type": "object",
            "required": ["campaign_id"],
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign to check",
                },
                "contact_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional: check specific contacts instead of "
                        "all campaign contacts"
                    ),
                },
                "strategy_id": {
                    "type": "string",
                    "description": (
                        "Optional: strategy to check against "
                        "(defaults to campaign's linked strategy)"
                    ),
                },
            },
        },
        handler=check_strategy_conflicts,
    ),
    ToolDefinition(
        name="get_campaign_summary",
        description=(
            "Get campaign stats and contact breakdown. Returns total "
            "contacts, contacts by status, enrichment readiness, and "
            "campaign metadata."
        ),
        input_schema={
            "type": "object",
            "required": ["campaign_id"],
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Campaign UUID to summarize",
                },
            },
        },
        handler=get_campaign_summary,
    ),
]

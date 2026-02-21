import json
import logging

from flask import Blueprint, current_app, g, jsonify, request

from ..auth import require_auth, require_role, resolve_tenant
from ..display import display_campaign_status, display_tier, display_status
from ..models import Campaign, CampaignContact, LinkedInSendQueue, db
from ..services.message_generator import estimate_generation_cost, start_generation
from ..services.send_service import get_send_status, send_campaign_emails

logger = logging.getLogger(__name__)

campaigns_bp = Blueprint("campaigns", __name__)

# Valid status transitions
VALID_TRANSITIONS = {
    "draft": {"ready", "archived"},
    "ready": {"draft", "generating"},
    "generating": {"review"},
    "review": {"approved", "ready"},
    "approved": {"exported", "review"},
    "exported": {"archived"},
}


def _format_ts(v):
    """Format a timestamp value that may be a datetime or a string."""
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _parse_jsonb(v):
    """Parse a JSONB column value — may be dict/list (PG) or str (SQLite)."""
    if v is None:
        return None
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return v
    return v


@campaigns_bp.route("/api/campaigns", methods=["GET"])
@require_auth
def list_campaigns():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    rows = db.session.execute(
        db.text("""
            SELECT
                c.id, c.name, c.status, c.description,
                c.total_contacts, c.generated_count, c.generation_cost,
                c.template_config, c.generation_config,
                c.created_at, c.updated_at,
                o.name AS owner_name
            FROM campaigns c
            LEFT JOIN owners o ON c.owner_id = o.id
            WHERE c.tenant_id = :t AND c.is_active = true
                AND COALESCE(c.status, 'draft') != 'archived'
            ORDER BY c.created_at DESC
        """),
        {"t": tenant_id},
    ).fetchall()

    campaigns = []
    for r in rows:
        campaigns.append(
            {
                "id": str(r[0]),
                "name": r[1],
                "status": display_campaign_status(r[2] or "draft"),
                "description": r[3],
                "total_contacts": r[4] or 0,
                "generated_count": r[5] or 0,
                "generation_cost": float(r[6]) if r[6] else 0,
                "template_config": _parse_jsonb(r[7]) or [],
                "generation_config": _parse_jsonb(r[8]) or {},
                "created_at": _format_ts(r[9]),
                "updated_at": _format_ts(r[10]),
                "owner_name": r[11],
            }
        )

    return jsonify({"campaigns": campaigns})


@campaigns_bp.route("/api/campaigns", methods=["POST"])
@require_role("editor")
def create_campaign():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    description = body.get("description", "")
    owner_id = body.get("owner_id")
    template_id = body.get("template_id")

    # If creating from a template, copy its steps and config
    template_config = []
    generation_config = {}
    if template_id:
        tpl = db.session.execute(
            db.text("""
                SELECT steps, default_config
                FROM campaign_templates
                WHERE id = :id AND (tenant_id = :t OR tenant_id IS NULL)
            """),
            {"id": template_id, "t": tenant_id},
        ).fetchone()
        if tpl:
            template_config = _parse_jsonb(tpl[0]) or []
            generation_config = _parse_jsonb(tpl[1]) or {}

    # Use ORM to avoid SQL dialect issues with JSONB casting
    campaign = Campaign(
        tenant_id=tenant_id,
        name=name,
        description=description,
        owner_id=owner_id,
        status="draft",
        template_config=json.dumps(template_config)
        if isinstance(template_config, (dict, list))
        else template_config,
        generation_config=json.dumps(generation_config)
        if isinstance(generation_config, (dict, list))
        else generation_config,
    )
    db.session.add(campaign)
    db.session.commit()

    return jsonify(
        {
            "id": str(campaign.id),
            "name": name,
            "status": "Draft",
            "created_at": _format_ts(campaign.created_at),
        }
    ), 201


@campaigns_bp.route("/api/campaigns/<campaign_id>", methods=["GET"])
@require_auth
def get_campaign(campaign_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    row = db.session.execute(
        db.text("""
            SELECT
                c.id, c.name, c.status, c.description,
                c.total_contacts, c.generated_count, c.generation_cost,
                c.template_config, c.generation_config,
                c.generation_started_at, c.generation_completed_at,
                c.created_at, c.updated_at,
                o.name AS owner_name, o.id AS owner_id,
                c.sender_config
            FROM campaigns c
            LEFT JOIN owners o ON c.owner_id = o.id
            WHERE c.id = :id AND c.tenant_id = :t
        """),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()

    if not row:
        return jsonify({"error": "Campaign not found"}), 404

    # Get contact status counts
    contact_stats = db.session.execute(
        db.text("""
            SELECT status, COUNT(*) AS cnt
            FROM campaign_contacts
            WHERE campaign_id = :id AND tenant_id = :t
            GROUP BY status
        """),
        {"id": campaign_id, "t": tenant_id},
    ).fetchall()

    status_counts = {r[0]: r[1] for r in contact_stats}

    return jsonify(
        {
            "id": str(row[0]),
            "name": row[1],
            "status": display_campaign_status(row[2] or "draft"),
            "description": row[3],
            "total_contacts": row[4] or 0,
            "generated_count": row[5] or 0,
            "generation_cost": float(row[6]) if row[6] else 0,
            "template_config": _parse_jsonb(row[7]) or [],
            "generation_config": _parse_jsonb(row[8]) or {},
            "generation_started_at": _format_ts(row[9]),
            "generation_completed_at": _format_ts(row[10]),
            "created_at": _format_ts(row[11]),
            "updated_at": _format_ts(row[12]),
            "owner_name": row[13],
            "owner_id": str(row[14]) if row[14] else None,
            "sender_config": _parse_jsonb(row[15]) or {},
            "contact_status_counts": status_counts,
        }
    )


@campaigns_bp.route("/api/campaigns/<campaign_id>", methods=["PATCH"])
@require_role("editor")
def update_campaign(campaign_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}

    # Verify campaign exists and belongs to tenant
    existing = db.session.execute(
        db.text("SELECT status FROM campaigns WHERE id = :id AND tenant_id = :t"),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()

    if not existing:
        return jsonify({"error": "Campaign not found"}), 404

    current_status = existing[0] or "draft"

    # Validate status transition if status is being updated
    new_status = body.get("status")
    if new_status:
        allowed = VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            return jsonify(
                {
                    "error": f"Cannot transition from '{current_status}' to '{new_status}'",
                    "allowed": sorted(allowed),
                }
            ), 400

        # Approval gate: review → approved requires no draft messages
        if current_status == "review" and new_status == "approved":
            draft_count = db.session.execute(
                db.text("""
                    SELECT COUNT(*) FROM messages m
                    JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
                    WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
                        AND m.status = 'draft'
                """),
                {"cid": campaign_id, "t": tenant_id},
            ).scalar()
            if draft_count > 0:
                return jsonify(
                    {
                        "error": f"Cannot approve: {draft_count} messages still in draft status",
                        "pending_count": draft_count,
                    }
                ), 400

    allowed_fields = {
        "name",
        "description",
        "status",
        "owner_id",
        "template_config",
        "generation_config",
        "sender_config",
    }
    fields = {k: v for k, v in body.items() if k in allowed_fields}

    if not fields:
        return jsonify({"error": "No valid fields to update"}), 400

    set_parts = []
    params = {"id": campaign_id, "t": tenant_id}
    for k, v in fields.items():
        if k in ("template_config", "generation_config", "sender_config"):
            set_parts.append(f"{k} = :{k}")
            params[k] = json.dumps(v) if isinstance(v, (dict, list)) else v
        else:
            set_parts.append(f"{k} = :{k}")
            params[k] = v

    db.session.execute(
        db.text(
            f"UPDATE campaigns SET {', '.join(set_parts)} WHERE id = :id AND tenant_id = :t"
        ),
        params,
    )
    db.session.commit()

    return jsonify({"ok": True})


@campaigns_bp.route("/api/campaigns/<campaign_id>", methods=["DELETE"])
@require_role("editor")
def delete_campaign(campaign_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    existing = db.session.execute(
        db.text("SELECT status FROM campaigns WHERE id = :id AND tenant_id = :t"),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()

    if not existing:
        return jsonify({"error": "Campaign not found"}), 404

    current_status = existing[0] or "draft"
    if current_status != "draft":
        return jsonify({"error": "Only draft campaigns can be deleted"}), 400

    # Soft delete: set status to archived and is_active to false
    db.session.execute(
        db.text("""
            UPDATE campaigns
            SET status = 'archived', is_active = false
            WHERE id = :id AND tenant_id = :t
        """),
        {"id": campaign_id, "t": tenant_id},
    )
    db.session.commit()

    return jsonify({"ok": True})


# ── Campaign Templates ────────────────────────────────────────


@campaigns_bp.route("/api/campaign-templates", methods=["GET"])
@require_auth
def list_campaign_templates():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    rows = db.session.execute(
        db.text("""
            SELECT id, name, description, steps, default_config, is_system, created_at
            FROM campaign_templates
            WHERE tenant_id = :t OR tenant_id IS NULL
            ORDER BY is_system DESC, name
        """),
        {"t": tenant_id},
    ).fetchall()

    templates = []
    for r in rows:
        templates.append(
            {
                "id": str(r[0]),
                "name": r[1],
                "description": r[2],
                "steps": _parse_jsonb(r[3]) or [],
                "default_config": _parse_jsonb(r[4]) or {},
                "is_system": bool(r[5]),
                "created_at": _format_ts(r[6]),
            }
        )

    return jsonify({"templates": templates})


# ── Campaign Contacts ─────────────────────────────────────────


@campaigns_bp.route("/api/campaigns/<campaign_id>/contacts", methods=["GET"])
@require_auth
def list_campaign_contacts(campaign_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    # Verify campaign exists
    campaign = db.session.execute(
        db.text("SELECT id FROM campaigns WHERE id = :id AND tenant_id = :t"),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    rows = db.session.execute(
        db.text("""
            SELECT
                cc.id, cc.status, cc.enrichment_gaps, cc.generation_cost, cc.error,
                cc.added_at, cc.generated_at,
                ct.id AS contact_id, ct.first_name, ct.last_name, ct.job_title,
                ct.email_address, ct.linkedin_url, ct.contact_score, ct.icp_fit,
                co.id AS company_id, co.name AS company_name, co.tier, co.status AS company_status
            FROM campaign_contacts cc
            JOIN contacts ct ON cc.contact_id = ct.id
            LEFT JOIN companies co ON ct.company_id = co.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            ORDER BY ct.contact_score DESC NULLS LAST, ct.last_name
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()

    contacts = []
    for r in rows:
        contacts.append(
            {
                "campaign_contact_id": str(r[0]),
                "status": r[1],
                "enrichment_gaps": _parse_jsonb(r[2]) or [],
                "generation_cost": float(r[3]) if r[3] else 0,
                "error": r[4],
                "added_at": _format_ts(r[5]),
                "generated_at": _format_ts(r[6]),
                "contact_id": str(r[7]),
                "first_name": r[8],
                "last_name": r[9],
                "full_name": ((r[8] or "") + " " + (r[9] or "")).strip(),
                "job_title": r[10],
                "email_address": r[11],
                "linkedin_url": r[12],
                "contact_score": r[13],
                "icp_fit": r[14],
                "company_id": str(r[15]) if r[15] else None,
                "company_name": r[16],
                "company_tier": r[17],
                "company_status": r[18],
            }
        )

    return jsonify({"contacts": contacts, "total": len(contacts)})


def _resolve_contacts_by_filters(tenant_id, owner_id, icp_filters, company_ids):
    """Resolve contact IDs from owner_id, ICP filters, and company_ids.

    Builds a dynamic SQL query joining contacts and companies to find
    contacts matching the criteria.  Returns a list of contact ID strings.
    """
    where = [
        "ct.tenant_id = :t",
        "(ct.is_disqualified = false OR ct.is_disqualified IS NULL)",
    ]
    params = {"t": tenant_id}

    if owner_id:
        where.append("ct.owner_id = :owner_id")
        params["owner_id"] = owner_id

    if company_ids:
        ph = ", ".join(f":comp_{i}" for i in range(len(company_ids)))
        for i, v in enumerate(company_ids):
            params[f"comp_{i}"] = v
        where.append(f"ct.company_id IN ({ph})")

    if icp_filters:
        # Tier filter (on company)
        tiers = icp_filters.get("tiers", [])
        if tiers:
            ph = ", ".join(f":tier_{i}" for i in range(len(tiers)))
            for i, v in enumerate(tiers):
                params[f"tier_{i}"] = v
            where.append(f"co.tier IN ({ph})")

        # Industry filter (on company)
        industries = icp_filters.get("industries", [])
        if industries:
            ph = ", ".join(f":ind_{i}" for i in range(len(industries)))
            for i, v in enumerate(industries):
                params[f"ind_{i}"] = v
            where.append(f"co.industry IN ({ph})")

        # ICP fit filter (on contact)
        icp_fit_values = icp_filters.get("icp_fit", [])
        if icp_fit_values:
            ph = ", ".join(f":icp_{i}" for i in range(len(icp_fit_values)))
            for i, v in enumerate(icp_fit_values):
                params[f"icp_{i}"] = v
            where.append(f"ct.icp_fit IN ({ph})")

        # Seniority filter (on contact)
        seniority_levels = icp_filters.get("seniority_levels", [])
        if seniority_levels:
            ph = ", ".join(f":sen_{i}" for i in range(len(seniority_levels)))
            for i, v in enumerate(seniority_levels):
                params[f"sen_{i}"] = v
            where.append(f"ct.seniority_level IN ({ph})")

        # Tag filter (on contact via contact_tag_assignments)
        tag_ids = icp_filters.get("tag_ids", [])
        if tag_ids:
            ph = ", ".join(f":tag_{i}" for i in range(len(tag_ids)))
            for i, v in enumerate(tag_ids):
                params[f"tag_{i}"] = v
            where.append(f"""EXISTS (
                SELECT 1 FROM contact_tag_assignments cta
                WHERE cta.contact_id = ct.id AND cta.tag_id IN ({ph})
            )""")

        # Min contact score
        min_score = icp_filters.get("min_contact_score")
        if min_score is not None:
            where.append("ct.contact_score >= :min_score")
            params["min_score"] = min_score

        # Enrichment readiness filter
        if icp_filters.get("enrichment_ready"):
            where.append("""EXISTS (
                SELECT 1 FROM entity_stage_completions esc_l1
                WHERE esc_l1.entity_id = co.id AND esc_l1.tenant_id = :t
                    AND esc_l1.stage = 'l1_company' AND esc_l1.status = 'completed'
            )""")
            where.append("""EXISTS (
                SELECT 1 FROM entity_stage_completions esc_l2
                WHERE esc_l2.entity_id = co.id AND esc_l2.tenant_id = :t
                    AND esc_l2.stage = 'l2_deep_research' AND esc_l2.status = 'completed'
            )""")
            where.append("""EXISTS (
                SELECT 1 FROM entity_stage_completions esc_p
                WHERE esc_p.entity_id = ct.id AND esc_p.tenant_id = :t
                    AND esc_p.stage = 'person' AND esc_p.status = 'completed'
            )""")

    where_clause = " AND ".join(where)
    rows = db.session.execute(
        db.text(f"""
            SELECT ct.id FROM contacts ct
            LEFT JOIN companies co ON ct.company_id = co.id
            WHERE {where_clause}
        """),
        params,
    ).fetchall()
    return [str(r[0]) for r in rows]


def _check_enrichment_gaps(tenant_id, contact_ids):
    """Check enrichment readiness for a set of contacts.

    Returns a list of dicts with contact_id, contact_name, and missing stages.
    Only contacts with gaps are included.
    """
    if not contact_ids:
        return []

    # Load contact + company info
    ph = ", ".join(f":cid_{i}" for i in range(len(contact_ids)))
    params = {f"cid_{i}": v for i, v in enumerate(contact_ids)}
    params["t"] = tenant_id
    contacts = db.session.execute(
        db.text(f"""
            SELECT ct.id, ct.first_name, ct.last_name, ct.company_id
            FROM contacts ct
            WHERE ct.tenant_id = :t AND ct.id IN ({ph})
        """),
        params,
    ).fetchall()

    if not contacts:
        return []

    # Build entity IDs for stage completion lookup
    company_ids_set = list({str(r[3]) for r in contacts if r[3]})
    all_entity_ids = list(set(contact_ids) | set(company_ids_set))

    completions = {}
    if all_entity_ids:
        eph = ", ".join(f":eid_{i}" for i in range(len(all_entity_ids)))
        eparams = {f"eid_{i}": v for i, v in enumerate(all_entity_ids)}
        eparams["t"] = tenant_id
        rows = db.session.execute(
            db.text(f"""
                SELECT entity_id, stage
                FROM entity_stage_completions
                WHERE tenant_id = :t AND status = 'completed'
                    AND entity_id IN ({eph})
            """),
            eparams,
        ).fetchall()
        for r in rows:
            completions.setdefault(str(r[0]), set()).add(r[1])

    gaps = []
    for row in contacts:
        cid, first_name, last_name, company_id = row
        missing = []
        company_stages = (
            completions.get(str(company_id), set()) if company_id else set()
        )
        contact_stages = completions.get(str(cid), set())

        if "l1_company" not in company_stages:
            missing.append("l1_company")
        if "l2_deep_research" not in company_stages:
            missing.append("l2_deep_research")
        if "person" not in contact_stages:
            missing.append("person")

        if missing:
            full_name = ((first_name or "") + " " + (last_name or "")).strip()
            gaps.append(
                {
                    "contact_id": str(cid),
                    "contact_name": full_name,
                    "missing": missing,
                }
            )

    return gaps


@campaigns_bp.route("/api/campaigns/<campaign_id>/contacts", methods=["POST"])
@require_role("editor")
def add_campaign_contacts(campaign_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    # Verify campaign exists and is in draft or ready state
    campaign = db.session.execute(
        db.text("SELECT status FROM campaigns WHERE id = :id AND tenant_id = :t"),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404
    if campaign[0] not in ("draft", "ready"):
        return jsonify(
            {"error": "Can only add contacts to draft or ready campaigns"}
        ), 400

    body = request.get_json(silent=True) or {}
    contact_ids = body.get("contact_ids", [])
    company_ids = body.get("company_ids", [])
    owner_id = body.get("owner_id")
    icp_filters = body.get("icp_filters")

    has_explicit = bool(contact_ids or company_ids)
    has_filters = bool(owner_id or icp_filters)

    if not has_explicit and not has_filters:
        return jsonify(
            {"error": "contact_ids, company_ids, owner_id, or icp_filters required"}
        ), 400

    # Resolve contacts from ICP filters and/or owner_id
    if has_filters:
        filter_company_ids = company_ids if company_ids else []
        resolved_ids = _resolve_contacts_by_filters(
            tenant_id, owner_id, icp_filters, filter_company_ids
        )
        # Merge with explicit contact_ids (deduplicate)
        contact_ids = list(set(contact_ids + resolved_ids))
    elif company_ids:
        # Legacy path: resolve contacts from company_ids only
        cid_placeholders = ", ".join(f":cid_{i}" for i in range(len(company_ids)))
        cid_params = {f"cid_{i}": v for i, v in enumerate(company_ids)}
        cid_params["t"] = tenant_id
        company_contacts = db.session.execute(
            db.text(f"""
                SELECT id FROM contacts
                WHERE tenant_id = :t AND company_id IN ({cid_placeholders})
                    AND (is_disqualified = false OR is_disqualified IS NULL)
            """),
            cid_params,
        ).fetchall()
        contact_ids = list(set(contact_ids + [str(r[0]) for r in company_contacts]))

    if not contact_ids:
        return jsonify({"error": "No contacts found for given criteria"}), 400

    # Verify contacts belong to tenant
    id_placeholders = ", ".join(f":id_{i}" for i in range(len(contact_ids)))
    id_params = {f"id_{i}": v for i, v in enumerate(contact_ids)}
    id_params["t"] = tenant_id
    valid = db.session.execute(
        db.text(f"""
            SELECT id FROM contacts
            WHERE tenant_id = :t AND id IN ({id_placeholders})
                AND (is_disqualified = false OR is_disqualified IS NULL)
        """),
        id_params,
    ).fetchall()
    valid_ids = {str(r[0]) for r in valid}

    # Get existing assignments to skip duplicates
    existing = db.session.execute(
        db.text("""
            SELECT contact_id FROM campaign_contacts
            WHERE campaign_id = :cid AND tenant_id = :t
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()
    existing_ids = {str(r[0]) for r in existing}

    added = 0
    skipped = 0
    added_ids = []
    for cid in contact_ids:
        if cid not in valid_ids:
            continue
        if cid in existing_ids:
            skipped += 1
            continue
        cc = CampaignContact(
            campaign_id=campaign_id,
            contact_id=cid,
            tenant_id=tenant_id,
            status="pending",
        )
        db.session.add(cc)
        added += 1
        added_ids.append(cid)

    # Flush ORM inserts so the count subquery can see them
    if added > 0:
        db.session.flush()
        db.session.execute(
            db.text("""
                UPDATE campaigns
                SET total_contacts = (
                    SELECT COUNT(*) FROM campaign_contacts WHERE campaign_id = :cid
                )
                WHERE id = :cid
            """),
            {"cid": campaign_id},
        )

    db.session.commit()

    # Check enrichment readiness for newly added contacts
    enrichment_gaps = _check_enrichment_gaps(tenant_id, added_ids) if added_ids else []

    return jsonify(
        {
            "added": added,
            "skipped": skipped,
            "total": added + len(existing_ids),
            "gaps": enrichment_gaps,
        }
    )


@campaigns_bp.route("/api/campaigns/<campaign_id>/contacts", methods=["DELETE"])
@require_role("editor")
def remove_campaign_contacts(campaign_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    campaign = db.session.execute(
        db.text("SELECT status FROM campaigns WHERE id = :id AND tenant_id = :t"),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404
    if campaign[0] not in ("draft", "ready"):
        return jsonify(
            {"error": "Can only remove contacts from draft or ready campaigns"}
        ), 400

    body = request.get_json(silent=True) or {}
    contact_ids = body.get("contact_ids", [])
    if not contact_ids:
        return jsonify({"error": "contact_ids required"}), 400

    id_placeholders = ", ".join(f":id_{i}" for i in range(len(contact_ids)))
    del_params = {f"id_{i}": v for i, v in enumerate(contact_ids)}
    del_params["cid"] = campaign_id
    del_params["t"] = tenant_id
    result = db.session.execute(
        db.text(
            f"DELETE FROM campaign_contacts WHERE campaign_id = :cid AND tenant_id = :t AND contact_id IN ({id_placeholders})"
        ),
        del_params,
    )
    removed = result.rowcount

    # Update total_contacts count
    db.session.execute(
        db.text("""
            UPDATE campaigns
            SET total_contacts = (
                SELECT COUNT(*) FROM campaign_contacts WHERE campaign_id = :cid
            )
            WHERE id = :cid
        """),
        {"cid": campaign_id},
    )
    db.session.commit()

    return jsonify({"removed": removed})


# ── Enrichment Readiness Check ───────────────────────────


@campaigns_bp.route("/api/campaigns/<campaign_id>/enrichment-check", methods=["POST"])
@require_role("editor")
def enrichment_check(campaign_id):
    """Check enrichment readiness for all contacts in a campaign.

    For each contact, checks whether their company has completed L1 and L2
    enrichment stages, and whether the contact has completed person enrichment.
    Returns per-contact readiness and a summary.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    campaign = db.session.execute(
        db.text("SELECT id FROM campaigns WHERE id = :id AND tenant_id = :t"),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    # Get all campaign contacts with their company info
    contacts = db.session.execute(
        db.text("""
            SELECT
                cc.id AS cc_id, cc.contact_id, cc.status AS cc_status,
                ct.company_id, ct.first_name, ct.last_name,
                co.name AS company_name
            FROM campaign_contacts cc
            JOIN contacts ct ON cc.contact_id = ct.id
            LEFT JOIN companies co ON ct.company_id = co.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()

    if not contacts:
        return jsonify(
            {
                "contacts": [],
                "summary": {"total": 0, "ready": 0, "needs_enrichment": 0},
            }
        )

    # Get all completed stages for relevant entities
    company_ids = list({str(r[3]) for r in contacts if r[3]})
    contact_ids = list({str(r[1]) for r in contacts})

    # Build completions lookup: entity_id -> set of completed stages
    completions = {}
    if company_ids or contact_ids:
        all_entity_ids = company_ids + contact_ids
        ph = ", ".join(f":eid_{i}" for i in range(len(all_entity_ids)))
        params = {f"eid_{i}": v for i, v in enumerate(all_entity_ids)}
        params["t"] = tenant_id
        rows = db.session.execute(
            db.text(f"""
                SELECT entity_id, stage
                FROM entity_stage_completions
                WHERE tenant_id = :t AND status = 'completed' AND entity_id IN ({ph})
            """),
            params,
        ).fetchall()
        for r in rows:
            eid = str(r[0])
            completions.setdefault(eid, set()).add(r[1])

    # Check each contact's readiness
    result_contacts = []
    ready_count = 0
    needs_enrichment_count = 0

    for row in contacts:
        (
            cc_id,
            contact_id,
            cc_status,
            company_id,
            first_name,
            last_name,
            company_name,
        ) = row
        gaps = []
        company_stages = (
            completions.get(str(company_id), set()) if company_id else set()
        )
        contact_stages = completions.get(str(contact_id), set())

        if "l1_company" not in company_stages:
            gaps.append("l1_company")
        if "l2_deep_research" not in company_stages:
            gaps.append("l2_deep_research")
        if "person" not in contact_stages:
            gaps.append("person")

        is_ready = len(gaps) == 0
        if is_ready:
            ready_count += 1
        else:
            needs_enrichment_count += 1

        # Update campaign_contact status
        new_status = "enrichment_ok" if is_ready else "enrichment_needed"
        if cc_status in ("pending", "enrichment_ok", "enrichment_needed"):
            db.session.execute(
                db.text("""
                    UPDATE campaign_contacts
                    SET status = :s, enrichment_gaps = :g
                    WHERE id = :id
                """),
                {"s": new_status, "g": json.dumps(gaps), "id": cc_id},
            )

        result_contacts.append(
            {
                "campaign_contact_id": str(cc_id),
                "contact_id": str(contact_id),
                "full_name": ((first_name or "") + " " + (last_name or "")).strip(),
                "company_name": company_name,
                "ready": is_ready,
                "gaps": gaps,
            }
        )

    db.session.commit()

    return jsonify(
        {
            "contacts": result_contacts,
            "summary": {
                "total": len(contacts),
                "ready": ready_count,
                "needs_enrichment": needs_enrichment_count,
            },
        }
    )


# ── Generation Pipeline ──────────────────────────────────


@campaigns_bp.route("/api/campaigns/<campaign_id>/cost-estimate", methods=["POST"])
@require_role("editor")
def generation_cost_estimate(campaign_id):
    """Estimate the cost of generating messages for this campaign."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    row = db.session.execute(
        db.text("""
            SELECT template_config, total_contacts
            FROM campaigns WHERE id = :id AND tenant_id = :t
        """),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()

    if not row:
        return jsonify({"error": "Campaign not found"}), 404

    template_config = _parse_jsonb(row[0]) or []
    total_contacts = row[1] or 0

    if total_contacts == 0:
        return jsonify({"error": "No contacts in campaign"}), 400

    enabled = [s for s in template_config if s.get("enabled")]
    if not enabled:
        return jsonify({"error": "No enabled message steps"}), 400

    estimate = estimate_generation_cost(template_config, total_contacts)
    return jsonify(estimate)


@campaigns_bp.route("/api/campaigns/<campaign_id>/generate", methods=["POST"])
@require_role("editor")
def start_campaign_generation(campaign_id):
    """Start message generation for a campaign (background)."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    row = db.session.execute(
        db.text(
            "SELECT status, total_contacts, template_config FROM campaigns WHERE id = :id AND tenant_id = :t"
        ),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()

    if not row:
        return jsonify({"error": "Campaign not found"}), 404

    current_status = row[0] or "draft"
    total_contacts = row[1] or 0
    template_config = _parse_jsonb(row[2]) or []

    # Must be in ready status to start generation
    if current_status != "ready":
        return jsonify(
            {
                "error": f"Campaign must be in 'ready' status to generate (current: {current_status})"
            }
        ), 400

    if total_contacts == 0:
        return jsonify({"error": "No contacts in campaign"}), 400

    enabled = [s for s in template_config if s.get("enabled")]
    if not enabled:
        return jsonify({"error": "No enabled message steps"}), 400

    # Transition to generating
    db.session.execute(
        db.text("""
            UPDATE campaigns
            SET status = 'generating', generation_started_at = CURRENT_TIMESTAMP,
                generated_count = 0, generation_cost = 0
            WHERE id = :id
        """),
        {"id": campaign_id},
    )
    db.session.commit()

    # Get user_id from auth context
    user_id = getattr(g, "user_id", None)

    # Start background generation
    start_generation(current_app._get_current_object(), campaign_id, tenant_id, user_id)

    return jsonify({"ok": True, "status": "generating"})


@campaigns_bp.route("/api/campaigns/<campaign_id>/generation-status", methods=["GET"])
@require_auth
def generation_status(campaign_id):
    """Poll generation progress for a campaign."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    row = db.session.execute(
        db.text("""
            SELECT status, total_contacts, generated_count, generation_cost,
                   generation_started_at, generation_completed_at,
                   template_config
            FROM campaigns WHERE id = :id AND tenant_id = :t
        """),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()

    if not row:
        return jsonify({"error": "Campaign not found"}), 404

    total = row[1] or 0
    generated = row[2] or 0
    template_config = _parse_jsonb(row[6]) or []

    # Count per-contact statuses
    contact_stats = db.session.execute(
        db.text("""
            SELECT status, COUNT(*) FROM campaign_contacts
            WHERE campaign_id = :id AND tenant_id = :t
            GROUP BY status
        """),
        {"id": campaign_id, "t": tenant_id},
    ).fetchall()
    status_counts = {r[0]: r[1] for r in contact_stats}

    # Channel breakdown: count generated messages per channel vs target
    enabled_steps = [s for s in template_config if s.get("enabled")]
    channels = {}
    if enabled_steps and total > 0:
        # Target per channel = contacts * steps with that channel
        channel_step_counts = {}
        for step in enabled_steps:
            ch = step.get("channel", "unknown")
            channel_step_counts[ch] = channel_step_counts.get(ch, 0) + 1

        for ch, step_count in channel_step_counts.items():
            channels[ch] = {"generated": 0, "target": total * step_count}

        # Count actual generated messages per channel
        msg_channel_stats = db.session.execute(
            db.text("""
                SELECT m.channel, COUNT(*)
                FROM messages m
                JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
                WHERE cc.campaign_id = :id AND cc.tenant_id = :t
                    AND m.status != 'failed'
                GROUP BY m.channel
            """),
            {"id": campaign_id, "t": tenant_id},
        ).fetchall()
        for ch, cnt in msg_channel_stats:
            if ch in channels:
                channels[ch]["generated"] = cnt
            else:
                channels[ch] = {"generated": cnt, "target": cnt}

    # Failed contacts with error details
    failed_rows = db.session.execute(
        db.text("""
            SELECT cc.contact_id, ct.first_name, ct.last_name, cc.error
            FROM campaign_contacts cc
            JOIN contacts ct ON cc.contact_id = ct.id
            WHERE cc.campaign_id = :id AND cc.tenant_id = :t
                AND cc.status = 'failed'
        """),
        {"id": campaign_id, "t": tenant_id},
    ).fetchall()
    failed_contacts = [
        {
            "contact_id": str(r[0]),
            "name": ((r[1] or "") + " " + (r[2] or "")).strip(),
            "error": r[3] or "Generation error",
        }
        for r in failed_rows
    ]

    return jsonify(
        {
            "status": display_campaign_status(row[0] or "draft"),
            "total_contacts": total,
            "generated_count": generated,
            "generation_cost": float(row[3]) if row[3] else 0,
            "progress_pct": round(generated / total * 100) if total > 0 else 0,
            "generation_started_at": _format_ts(row[4]),
            "generation_completed_at": _format_ts(row[5]),
            "contact_statuses": status_counts,
            "channels": channels,
            "failed_contacts": failed_contacts,
        }
    )


@campaigns_bp.route("/api/campaigns/<campaign_id>/generate", methods=["DELETE"])
@require_role("editor")
def cancel_campaign_generation(campaign_id):
    """Cancel an active generation by setting the cancelled flag.

    The background generator checks this flag between messages and stops
    gracefully. Campaign status reverts to 'ready' so generation can be
    restarted later.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    row = db.session.execute(
        db.text(
            "SELECT status, generation_config FROM campaigns WHERE id = :id AND tenant_id = :t"
        ),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()

    if not row:
        return jsonify({"error": "Campaign not found"}), 404

    current_status = row[0] or "draft"
    if current_status != "generating":
        return jsonify(
            {"error": f"Campaign is not generating (current: {current_status})"}
        ), 400

    # Set cancelled flag in generation_config so the background thread stops
    gen_config = _parse_jsonb(row[1]) or {}
    gen_config["cancelled"] = True

    db.session.execute(
        db.text("""
            UPDATE campaigns
            SET generation_config = :gc, status = 'ready'
            WHERE id = :id AND tenant_id = :t
        """),
        {
            "gc": json.dumps(gen_config),
            "id": campaign_id,
            "t": tenant_id,
        },
    )
    db.session.commit()

    return jsonify({"ok": True, "status": "cancelled"})


# --- T6: Disqualify contact ---


@campaigns_bp.route("/api/campaigns/<campaign_id>/disqualify-contact", methods=["POST"])
@require_role("editor")
def disqualify_contact(campaign_id):
    """Disqualify a contact from a campaign (campaign-only or global)."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    contact_id = body.get("contact_id")
    scope = body.get("scope", "campaign")
    reason = body.get("reason")

    if not contact_id:
        return jsonify({"error": "contact_id required"}), 400
    if scope not in ("campaign", "global"):
        return jsonify({"error": "scope must be 'campaign' or 'global'"}), 400

    # Verify campaign_contact exists
    cc = db.session.execute(
        db.text("""
            SELECT id FROM campaign_contacts
            WHERE campaign_id = :cid AND contact_id = :ctid AND tenant_id = :t
        """),
        {"cid": campaign_id, "ctid": contact_id, "t": tenant_id},
    ).fetchone()
    if not cc:
        return jsonify({"error": "Contact not in this campaign"}), 404

    cc_id = cc[0]

    # Campaign exclusion: set campaign_contact to excluded, reject all messages
    db.session.execute(
        db.text(
            "UPDATE campaign_contacts SET status = 'excluded' WHERE id = :id AND tenant_id = :t"
        ),
        {"id": cc_id, "t": tenant_id},
    )
    result = db.session.execute(
        db.text("""
            UPDATE messages
            SET status = 'rejected',
                review_notes = 'Contact excluded from campaign',
                updated_at = CURRENT_TIMESTAMP
            WHERE campaign_contact_id = :cc_id AND status = 'draft'
        """),
        {"cc_id": cc_id},
    )
    messages_rejected = result.rowcount

    # Global disqualification
    if scope == "global":
        db.session.execute(
            db.text("""
                UPDATE contacts
                SET is_disqualified = true,
                    disqualified_at = CURRENT_TIMESTAMP,
                    disqualified_reason = :reason
                WHERE id = :id AND tenant_id = :t
            """),
            {"id": contact_id, "t": tenant_id, "reason": reason},
        )

    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "contact_id": contact_id,
            "scope": scope,
            "messages_rejected": messages_rejected,
        }
    )


# --- T7: Review summary + approval gate ---


@campaigns_bp.route("/api/campaigns/<campaign_id>/review-summary", methods=["GET"])
@require_auth
def review_summary(campaign_id):
    """Get review progress and approval readiness for a campaign."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    # Message status counts
    msg_stats = db.session.execute(
        db.text("""
            SELECT m.status, COUNT(*)
            FROM messages m
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            GROUP BY m.status
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()
    counts = {r[0]: r[1] for r in msg_stats}

    total = sum(counts.values())
    approved = counts.get("approved", 0)
    rejected = counts.get("rejected", 0)
    draft = counts.get("draft", 0)

    # Excluded contacts
    excluded = db.session.execute(
        db.text("""
            SELECT COUNT(*) FROM campaign_contacts
            WHERE campaign_id = :cid AND tenant_id = :t AND status = 'excluded'
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).scalar()

    active_contacts = db.session.execute(
        db.text("""
            SELECT COUNT(DISTINCT cc.contact_id)
            FROM campaign_contacts cc
            JOIN messages m ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
                AND cc.status != 'excluded' AND m.status = 'approved'
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).scalar()

    # Breakdown by channel
    channel_stats = db.session.execute(
        db.text("""
            SELECT m.channel, m.status, COUNT(*)
            FROM messages m
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            GROUP BY m.channel, m.status
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()

    by_channel = {}
    for ch, st, cnt in channel_stats:
        if ch not in by_channel:
            by_channel[ch] = {"approved": 0, "rejected": 0, "draft": 0}
        by_channel[ch][st] = by_channel[ch].get(st, 0) + cnt

    can_approve = draft == 0 and total > 0
    pending_reason = None
    if draft > 0:
        pending_reason = f"{draft} messages pending review"
    elif total == 0:
        pending_reason = "No messages generated"

    return jsonify(
        {
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "draft": draft,
            "excluded_contacts": excluded,
            "active_contacts": active_contacts,
            "by_channel": by_channel,
            "can_approve_outreach": can_approve,
            "pending_reason": pending_reason,
        }
    )


# --- T8: Review queue ---


@campaigns_bp.route("/api/campaigns/<campaign_id>/review-queue", methods=["GET"])
@require_auth
def review_queue(campaign_id):
    """Get ordered list of messages with full context for focused review."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    # Query params
    status_filter = request.args.get("status", "draft")
    channel_filter = request.args.get("channel")
    step_filter = request.args.get("step")

    where = ["cc.campaign_id = :cid", "cc.tenant_id = :t", "cc.status != 'excluded'"]
    params = {"cid": campaign_id, "t": tenant_id}

    if status_filter:
        where.append("m.status = :status")
        params["status"] = status_filter
    if channel_filter:
        where.append("m.channel = :channel")
        params["channel"] = channel_filter
    if step_filter:
        try:
            params["step"] = int(step_filter)
        except (ValueError, TypeError):
            return jsonify({"error": "step must be an integer"}), 400
        where.append("m.sequence_step = :step")

    where_clause = " AND ".join(where)

    rows = db.session.execute(
        db.text(f"""
            SELECT
                m.id, m.channel, m.sequence_step, m.variant,
                m.subject, m.body, m.status, m.tone, m.language,
                m.generation_cost_usd, m.review_notes, m.approved_at,
                m.original_body, m.original_subject, m.edit_reason,
                m.edit_reason_text, m.regen_count, m.regen_config,
                ct.id AS contact_id, ct.first_name, ct.last_name,
                ct.job_title, ct.email_address, ct.linkedin_url,
                ct.contact_score, ct.icp_fit, ct.seniority_level,
                ct.department, ct.location_country,
                co.id AS company_id, co.name AS company_name,
                co.domain, co.tier, co.industry, co.hq_country,
                co.summary AS company_summary, co.status AS company_status,
                m.label, m.campaign_contact_id
            FROM messages m
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            JOIN contacts ct ON m.contact_id = ct.id
            LEFT JOIN companies co ON ct.company_id = co.id
            WHERE {where_clause}
            ORDER BY ct.contact_score DESC NULLS LAST,
                     ct.id,
                     m.sequence_step ASC
        """),
        params,
    ).fetchall()

    # Queue stats (all messages in campaign, not filtered)
    stats = db.session.execute(
        db.text("""
            SELECT m.status, COUNT(*)
            FROM messages m
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
                AND cc.status != 'excluded'
            GROUP BY m.status
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()
    stat_counts = {r[0]: r[1] for r in stats}

    total_count = len(rows)
    messages = []
    for idx, r in enumerate(rows):
        regen_config = r[17]
        if isinstance(regen_config, str):
            try:
                regen_config = json.loads(regen_config)
            except (json.JSONDecodeError, TypeError):
                regen_config = None

        messages.append(
            {
                "position": idx + 1,
                "total": total_count,
                "message": {
                    "id": str(r[0]),
                    "channel": r[1],
                    "sequence_step": r[2],
                    "variant": (r[3] or "a").upper(),
                    "subject": r[4],
                    "body": r[5],
                    "status": r[6],
                    "tone": r[7],
                    "language": r[8],
                    "generation_cost": float(r[9]) if r[9] else None,
                    "review_notes": r[10],
                    "approved_at": _format_ts(r[11]),
                    "original_body": r[12],
                    "original_subject": r[13],
                    "edit_reason": r[14],
                    "edit_reason_text": r[15],
                    "regen_count": r[16] or 0,
                    "regen_config": regen_config,
                    "label": r[37],
                    "campaign_contact_id": str(r[38]),
                },
                "contact": {
                    "id": str(r[18]),
                    "first_name": r[19],
                    "last_name": r[20],
                    "full_name": ((r[19] or "") + " " + (r[20] or "")).strip(),
                    "job_title": r[21],
                    "email_address": r[22],
                    "linkedin_url": r[23],
                    "contact_score": r[24],
                    "icp_fit": r[25],
                    "seniority_level": r[26],
                    "department": r[27],
                    "location_country": r[28],
                },
                "company": {
                    "id": str(r[29]) if r[29] else None,
                    "name": r[30],
                    "domain": r[31],
                    "tier": display_tier(r[32]),
                    "industry": r[33],
                    "hq_country": r[34],
                    "summary": r[35],
                    "status": display_status(r[36]),
                }
                if r[29]
                else None,
            }
        )

    return jsonify(
        {
            "queue": messages,
            "stats": {
                "total": sum(stat_counts.values()),
                "approved": stat_counts.get("approved", 0),
                "rejected": stat_counts.get("rejected", 0),
                "draft": stat_counts.get("draft", 0),
            },
        }
    )


# --- Batch message actions (approve/reject) ---


@campaigns_bp.route(
    "/api/campaigns/<campaign_id>/messages/batch-action", methods=["POST"]
)
@require_role("editor")
def batch_message_action(campaign_id):
    """Batch approve or reject messages belonging to a campaign.

    Body: { message_ids: string[], action: "approve"|"reject", reason?: string }
    Response: { updated: N, action: "approve"|"reject", errors: [] }
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    message_ids = body.get("message_ids", [])
    action = body.get("action")
    reason = body.get("reason")

    # Validate inputs
    if not message_ids:
        return jsonify({"error": "message_ids is required and cannot be empty"}), 400
    if action not in ("approve", "reject"):
        return jsonify(
            {"error": "action must be 'approve' or 'reject'"}
        ), 400

    # Verify campaign exists and belongs to tenant
    campaign = db.session.execute(
        db.text("SELECT id FROM campaigns WHERE id = :id AND tenant_id = :t"),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    # Verify all message_ids belong to this campaign and tenant
    id_placeholders = ", ".join(f":mid_{i}" for i in range(len(message_ids)))
    id_params = {f"mid_{i}": v for i, v in enumerate(message_ids)}
    id_params["cid"] = campaign_id
    id_params["t"] = tenant_id

    valid_rows = db.session.execute(
        db.text(f"""
            SELECT m.id FROM messages m
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
                AND m.id IN ({id_placeholders})
        """),
        id_params,
    ).fetchall()
    valid_ids = {str(r[0]) for r in valid_rows}

    # Collect errors for invalid IDs
    errors = []
    for mid in message_ids:
        if mid not in valid_ids:
            errors.append(
                {"message_id": mid, "error": "Message not found in this campaign"}
            )

    if not valid_ids:
        return (
            jsonify(
                {
                    "updated": 0,
                    "action": action,
                    "errors": errors,
                }
            ),
            400,
        )

    # Build the update using individual placeholders (SQLite + PG compatible)
    valid_list = list(valid_ids)
    upd_placeholders = ", ".join(f":uid_{i}" for i in range(len(valid_list)))
    update_params = {f"uid_{i}": v for i, v in enumerate(valid_list)}
    update_params["t"] = tenant_id

    if action == "approve":
        db.session.execute(
            db.text(f"""
                UPDATE messages
                SET status = 'approved',
                    approved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = :t AND id IN ({upd_placeholders})
            """),
            update_params,
        )
    else:  # reject
        update_params["reason"] = reason or ""
        db.session.execute(
            db.text(f"""
                UPDATE messages
                SET status = 'rejected',
                    review_notes = :reason,
                    updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = :t AND id IN ({upd_placeholders})
            """),
            update_params,
        )

    db.session.commit()

    return jsonify(
        {
            "updated": len(valid_ids),
            "action": action,
            "errors": errors,
        }
    )


# --- Email send + status ---


@campaigns_bp.route("/api/campaigns/<campaign_id>/send-emails", methods=["POST"])
@require_role("editor")
def send_emails(campaign_id):
    """Send approved email messages for a campaign via Resend.

    Validates campaign has approved email messages and a sender_config.
    Starts the send in a background thread and returns immediately.

    Body: { confirm?: boolean }
    Response: { queued_count: N, sender: { from_email, from_name } }
    """
    import threading

    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    campaign = db.session.get(Campaign, campaign_id)
    if not campaign or str(campaign.tenant_id) != str(tenant_id):
        return jsonify({"error": "Campaign not found"}), 404

    # Validate sender_config
    sender_config = campaign.sender_config
    if isinstance(sender_config, str):
        sender_config = json.loads(sender_config)
    sender_config = sender_config or {}

    from_email = sender_config.get("from_email")
    if not from_email:
        return jsonify(
            {"error": "Campaign sender_config is missing from_email. Configure sender identity first."}
        ), 400

    # Validate tenant has Resend API key
    from ..models import Tenant

    tenant = db.session.get(Tenant, tenant_id)
    tenant_settings = tenant.settings if tenant else {}
    if isinstance(tenant_settings, str):
        tenant_settings = json.loads(tenant_settings)
    tenant_settings = tenant_settings or {}

    if not tenant_settings.get("resend_api_key"):
        return jsonify(
            {"error": "Tenant settings missing resend_api_key. Contact your admin."}
        ), 400

    # Count approved email messages not yet sent
    approved_count = db.session.execute(
        db.text("""
            SELECT COUNT(*) FROM messages m
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
                AND m.status = 'approved' AND m.channel = 'email'
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).scalar()

    if approved_count == 0:
        return jsonify({"error": "No approved email messages to send"}), 400

    # Start background send
    app = current_app._get_current_object()

    def _run_send():
        with app.app_context():
            try:
                result = send_campaign_emails(campaign_id, str(tenant_id))
                logger.info(
                    "Send completed for campaign %s: %s",
                    campaign_id,
                    result,
                )
            except Exception:
                logger.exception(
                    "Send failed for campaign %s", campaign_id
                )

    thread = threading.Thread(target=_run_send, daemon=True)
    thread.start()

    return jsonify(
        {
            "queued_count": approved_count,
            "sender": {
                "from_email": from_email,
                "from_name": sender_config.get("from_name"),
            },
        }
    )


@campaigns_bp.route("/api/campaigns/<campaign_id>/send-status", methods=["GET"])
@require_auth
def send_status(campaign_id):
    """Get email send status for a campaign.

    Response: { total, queued, sent, delivered, failed, bounced }
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    # Verify campaign exists
    campaign = db.session.execute(
        db.text("SELECT id FROM campaigns WHERE id = :id AND tenant_id = :t"),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    status = get_send_status(campaign_id, str(tenant_id))
    return jsonify(status)


# --- Queue LinkedIn messages for Chrome extension ---


@campaigns_bp.route("/api/campaigns/<campaign_id>/queue-linkedin", methods=["POST"])
@require_role("editor")
def queue_linkedin(campaign_id):
    """Queue approved LinkedIn messages for the Chrome extension to send.

    Finds all approved LinkedIn messages (linkedin_connect, linkedin_message)
    in this campaign and creates LinkedInSendQueue entries for each.
    Idempotent: re-queuing skips messages already in the queue.

    Returns: { queued_count: N, by_owner: { "Alice": 5, "Bob": 3 } }
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    # Verify campaign exists and belongs to tenant
    campaign = db.session.execute(
        db.text("SELECT id, status FROM campaigns WHERE id = :id AND tenant_id = :t"),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    # Load approved LinkedIn messages for this campaign
    rows = db.session.execute(
        db.text("""
            SELECT m.id, m.body, m.channel, m.contact_id, m.owner_id,
                   ct.linkedin_url, ct.first_name, ct.last_name
            FROM messages m
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            JOIN contacts ct ON m.contact_id = ct.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
                AND m.status = 'approved'
                AND m.channel IN ('linkedin_connect', 'linkedin_message')
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()

    if not rows:
        return jsonify({"queued_count": 0, "by_owner": {}})

    # Get already-queued message IDs (idempotency)
    message_ids = [str(r[0]) for r in rows]
    mid_placeholders = ", ".join(f":mid_{i}" for i in range(len(message_ids)))
    mid_params = {f"mid_{i}": v for i, v in enumerate(message_ids)}
    mid_params["t"] = tenant_id
    existing = db.session.execute(
        db.text(f"""
            SELECT message_id FROM linkedin_send_queue
            WHERE tenant_id = :t AND message_id IN ({mid_placeholders})
        """),
        mid_params,
    ).fetchall()
    existing_message_ids = {str(r[0]) for r in existing}

    # Map action_type from channel name
    channel_to_action = {
        "linkedin_connect": "connection_request",
        "linkedin_message": "message",
    }

    # Load owner names for the response
    owner_ids = list({str(r[4]) for r in rows if r[4]})
    owner_names = {}
    if owner_ids:
        oid_placeholders = ", ".join(f":oid_{i}" for i in range(len(owner_ids)))
        oid_params = {f"oid_{i}": v for i, v in enumerate(owner_ids)}
        owner_rows = db.session.execute(
            db.text(f"SELECT id, name FROM owners WHERE id IN ({oid_placeholders})"),
            oid_params,
        ).fetchall()
        owner_names = {str(r[0]): r[1] for r in owner_rows}

    queued_count = 0
    by_owner = {}

    for r in rows:
        msg_id = r[0]
        body = r[1]
        channel = r[2]
        contact_id = r[3]
        owner_id = r[4]
        linkedin_url = r[5]

        if str(msg_id) in existing_message_ids:
            continue

        if not owner_id:
            continue

        action_type = channel_to_action.get(channel, "message")

        entry = LinkedInSendQueue(
            tenant_id=str(tenant_id),
            message_id=str(msg_id),
            contact_id=str(contact_id),
            owner_id=str(owner_id),
            action_type=action_type,
            linkedin_url=linkedin_url,
            body=body,
            status="queued",
        )
        db.session.add(entry)
        queued_count += 1

        owner_name = owner_names.get(str(owner_id), str(owner_id))
        by_owner[owner_name] = by_owner.get(owner_name, 0) + 1

    db.session.commit()

    return jsonify({"queued_count": queued_count, "by_owner": by_owner})


# --- T8: Campaign analytics aggregation ---


@campaigns_bp.route("/api/campaigns/<campaign_id>/analytics", methods=["GET"])
@require_role("viewer")
def campaign_analytics(campaign_id):
    """Return aggregated campaign metrics for the OutreachTab / CampaignAnalytics component.

    Aggregates message counts, sending stats, contact stats, cost, and timeline.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    # Verify campaign exists and belongs to tenant
    campaign_row = db.session.execute(
        db.text("""
            SELECT id, generation_config, created_at,
                   generation_started_at, generation_completed_at
            FROM campaigns
            WHERE id = :id AND tenant_id = :t
        """),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()

    if not campaign_row:
        return jsonify({"error": "Campaign not found"}), 404

    gen_config = _parse_jsonb(campaign_row[1]) or {}
    campaign_created_at = campaign_row[2]
    generation_started_at = campaign_row[3]
    generation_completed_at = campaign_row[4]

    # ── Messages aggregation ─────────────────────────────────
    # By status
    msg_by_status_rows = db.session.execute(
        db.text("""
            SELECT m.status, COUNT(*)
            FROM messages m
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            GROUP BY m.status
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()
    msg_by_status = {r[0]: r[1] for r in msg_by_status_rows}
    msg_total = sum(msg_by_status.values())

    # By channel
    msg_by_channel_rows = db.session.execute(
        db.text("""
            SELECT m.channel, COUNT(*)
            FROM messages m
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            GROUP BY m.channel
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()
    msg_by_channel = {r[0]: r[1] for r in msg_by_channel_rows}

    # By step
    msg_by_step_rows = db.session.execute(
        db.text("""
            SELECT m.sequence_step, COUNT(*)
            FROM messages m
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            GROUP BY m.sequence_step
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()
    msg_by_step = {str(r[0]): r[1] for r in msg_by_step_rows}

    # ── Email sending stats ──────────────────────────────────
    email_send_rows = db.session.execute(
        db.text("""
            SELECT esl.status, COUNT(*)
            FROM email_send_log esl
            JOIN messages m ON esl.message_id = m.id
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            GROUP BY esl.status
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()
    email_counts = {r[0]: r[1] for r in email_send_rows}
    email_total = sum(email_counts.values())

    # ── LinkedIn sending stats ───────────────────────────────
    li_send_rows = db.session.execute(
        db.text("""
            SELECT lsq.status, COUNT(*)
            FROM linkedin_send_queue lsq
            JOIN messages m ON lsq.message_id = m.id
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            GROUP BY lsq.status
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchall()
    li_counts = {r[0]: r[1] for r in li_send_rows}
    li_total = sum(li_counts.values())

    # ── Contact stats ────────────────────────────────────────
    contact_stats_row = db.session.execute(
        db.text("""
            SELECT
                COUNT(DISTINCT cc.contact_id) AS total,
                COUNT(DISTINCT CASE WHEN ct.email_address IS NOT NULL AND ct.email_address != '' THEN cc.contact_id END) AS with_email,
                COUNT(DISTINCT CASE WHEN ct.linkedin_url IS NOT NULL AND ct.linkedin_url != '' THEN cc.contact_id END) AS with_linkedin,
                COUNT(DISTINCT CASE WHEN
                    (ct.email_address IS NOT NULL AND ct.email_address != '')
                    AND (ct.linkedin_url IS NOT NULL AND ct.linkedin_url != '')
                THEN cc.contact_id END) AS both_channels
            FROM campaign_contacts cc
            JOIN contacts ct ON cc.contact_id = ct.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchone()

    contacts_total = contact_stats_row[0] if contact_stats_row else 0
    contacts_with_email = contact_stats_row[1] if contact_stats_row else 0
    contacts_with_linkedin = contact_stats_row[2] if contact_stats_row else 0
    contacts_both = contact_stats_row[3] if contact_stats_row else 0

    # ── Cost ─────────────────────────────────────────────────
    cost_data = gen_config.get("cost", {})
    generation_cost_usd = float(cost_data.get("generation_usd", 0)) if isinstance(cost_data, dict) else 0

    # Also sum generation_cost_usd from messages as a fallback
    if generation_cost_usd == 0:
        cost_row = db.session.execute(
            db.text("""
                SELECT COALESCE(SUM(m.generation_cost_usd), 0)
                FROM messages m
                JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
                WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
            """),
            {"cid": campaign_id, "t": tenant_id},
        ).fetchone()
        generation_cost_usd = float(cost_row[0]) if cost_row else 0

    # ── Timeline ─────────────────────────────────────────────
    # First/last send timestamps from email_send_log
    send_times = db.session.execute(
        db.text("""
            SELECT MIN(esl.sent_at), MAX(esl.sent_at)
            FROM email_send_log esl
            JOIN messages m ON esl.message_id = m.id
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
                AND esl.sent_at IS NOT NULL
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchone()

    first_send_at = send_times[0] if send_times else None
    last_send_at = send_times[1] if send_times else None

    # Also check linkedin_send_queue for first/last send
    li_send_times = db.session.execute(
        db.text("""
            SELECT MIN(lsq.sent_at), MAX(lsq.sent_at)
            FROM linkedin_send_queue lsq
            JOIN messages m ON lsq.message_id = m.id
            JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE cc.campaign_id = :cid AND cc.tenant_id = :t
                AND lsq.sent_at IS NOT NULL
        """),
        {"cid": campaign_id, "t": tenant_id},
    ).fetchone()

    if li_send_times and li_send_times[0]:
        if first_send_at is None or li_send_times[0] < first_send_at:
            first_send_at = li_send_times[0]
        if last_send_at is None or li_send_times[1] > last_send_at:
            last_send_at = li_send_times[1]

    return jsonify({
        "messages": {
            "total": msg_total,
            "by_status": msg_by_status,
            "by_channel": msg_by_channel,
            "by_step": msg_by_step,
        },
        "sending": {
            "email": {
                "total": email_total,
                "queued": email_counts.get("queued", 0),
                "sent": email_counts.get("sent", 0),
                "delivered": email_counts.get("delivered", 0),
                "bounced": email_counts.get("bounced", 0),
                "failed": email_counts.get("failed", 0),
            },
            "linkedin": {
                "total": li_total,
                "queued": li_counts.get("queued", 0),
                "sent": li_counts.get("sent", 0),
                "delivered": li_counts.get("delivered", 0),
                "failed": li_counts.get("failed", 0),
            },
        },
        "contacts": {
            "total": contacts_total,
            "with_email": contacts_with_email,
            "with_linkedin": contacts_with_linkedin,
            "both_channels": contacts_both,
        },
        "cost": {
            "generation_usd": generation_cost_usd,
            "email_sends": email_total,
        },
        "timeline": {
            "created_at": _format_ts(campaign_created_at),
            "generation_started_at": _format_ts(generation_started_at),
            "generation_completed_at": _format_ts(generation_completed_at),
            "first_send_at": _format_ts(first_send_at),
            "last_send_at": _format_ts(last_send_at),
        },
    })

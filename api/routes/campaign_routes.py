import json

from flask import Blueprint, jsonify, request

from flask import current_app

from ..auth import require_auth, require_role, resolve_tenant
from ..display import display_campaign_status
from ..models import Campaign, CampaignContact, CampaignTemplate, db
from ..services.message_generator import estimate_generation_cost, start_generation

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
        campaigns.append({
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
        })

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
        template_config=json.dumps(template_config) if isinstance(template_config, (dict, list)) else template_config,
        generation_config=json.dumps(generation_config) if isinstance(generation_config, (dict, list)) else generation_config,
    )
    db.session.add(campaign)
    db.session.commit()

    return jsonify({
        "id": str(campaign.id),
        "name": name,
        "status": "Draft",
        "created_at": _format_ts(campaign.created_at),
    }), 201


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
                o.name AS owner_name, o.id AS owner_id
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

    return jsonify({
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
        "contact_status_counts": status_counts,
    })


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
            return jsonify({
                "error": f"Cannot transition from '{current_status}' to '{new_status}'",
                "allowed": sorted(allowed),
            }), 400

    allowed_fields = {
        "name", "description", "status", "owner_id",
        "template_config", "generation_config",
    }
    fields = {k: v for k, v in body.items() if k in allowed_fields}

    if not fields:
        return jsonify({"error": "No valid fields to update"}), 400

    set_parts = []
    params = {"id": campaign_id, "t": tenant_id}
    for k, v in fields.items():
        if k in ("template_config", "generation_config"):
            set_parts.append(f"{k} = :{k}")
            params[k] = json.dumps(v) if isinstance(v, (dict, list)) else v
        else:
            set_parts.append(f"{k} = :{k}")
            params[k] = v

    db.session.execute(
        db.text(f"UPDATE campaigns SET {', '.join(set_parts)} WHERE id = :id AND tenant_id = :t"),
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
        templates.append({
            "id": str(r[0]),
            "name": r[1],
            "description": r[2],
            "steps": _parse_jsonb(r[3]) or [],
            "default_config": _parse_jsonb(r[4]) or {},
            "is_system": bool(r[5]),
            "created_at": _format_ts(r[6]),
        })

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
        contacts.append({
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
        })

    return jsonify({"contacts": contacts, "total": len(contacts)})


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
        return jsonify({"error": "Can only add contacts to draft or ready campaigns"}), 400

    body = request.get_json(silent=True) or {}
    contact_ids = body.get("contact_ids", [])
    company_ids = body.get("company_ids", [])

    if not contact_ids and not company_ids:
        return jsonify({"error": "contact_ids or company_ids required"}), 400

    # If company_ids provided, resolve all contacts for those companies
    if company_ids:
        cid_placeholders = ", ".join(f":cid_{i}" for i in range(len(company_ids)))
        cid_params = {f"cid_{i}": v for i, v in enumerate(company_ids)}
        cid_params["t"] = tenant_id
        company_contacts = db.session.execute(
            db.text(f"SELECT id FROM contacts WHERE tenant_id = :t AND company_id IN ({cid_placeholders})"),
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
        db.text(f"SELECT id FROM contacts WHERE tenant_id = :t AND id IN ({id_placeholders})"),
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

    return jsonify({"added": added, "skipped": skipped, "total": added + len(existing_ids)})


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
        return jsonify({"error": "Can only remove contacts from draft or ready campaigns"}), 400

    body = request.get_json(silent=True) or {}
    contact_ids = body.get("contact_ids", [])
    if not contact_ids:
        return jsonify({"error": "contact_ids required"}), 400

    id_placeholders = ", ".join(f":id_{i}" for i in range(len(contact_ids)))
    del_params = {f"id_{i}": v for i, v in enumerate(contact_ids)}
    del_params["cid"] = campaign_id
    del_params["t"] = tenant_id
    result = db.session.execute(
        db.text(f"DELETE FROM campaign_contacts WHERE campaign_id = :cid AND tenant_id = :t AND contact_id IN ({id_placeholders})"),
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
        return jsonify({
            "contacts": [],
            "summary": {"total": 0, "ready": 0, "needs_enrichment": 0},
        })

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
        cc_id, contact_id, cc_status, company_id, first_name, last_name, company_name = row
        gaps = []
        company_stages = completions.get(str(company_id), set()) if company_id else set()
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

        result_contacts.append({
            "campaign_contact_id": str(cc_id),
            "contact_id": str(contact_id),
            "full_name": ((first_name or "") + " " + (last_name or "")).strip(),
            "company_name": company_name,
            "ready": is_ready,
            "gaps": gaps,
        })

    db.session.commit()

    return jsonify({
        "contacts": result_contacts,
        "summary": {
            "total": len(contacts),
            "ready": ready_count,
            "needs_enrichment": needs_enrichment_count,
        },
    })


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
        db.text("SELECT status, total_contacts, template_config FROM campaigns WHERE id = :id AND tenant_id = :t"),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()

    if not row:
        return jsonify({"error": "Campaign not found"}), 404

    current_status = row[0] or "draft"
    total_contacts = row[1] or 0
    template_config = _parse_jsonb(row[2]) or []

    # Must be in ready status to start generation
    if current_status != "ready":
        return jsonify({"error": f"Campaign must be in 'ready' status to generate (current: {current_status})"}), 400

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
    from flask import g
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
                   generation_started_at, generation_completed_at
            FROM campaigns WHERE id = :id AND tenant_id = :t
        """),
        {"id": campaign_id, "t": tenant_id},
    ).fetchone()

    if not row:
        return jsonify({"error": "Campaign not found"}), 404

    total = row[1] or 0
    generated = row[2] or 0

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

    return jsonify({
        "status": display_campaign_status(row[0] or "draft"),
        "total_contacts": total,
        "generated_count": generated,
        "generation_cost": float(row[3]) if row[3] else 0,
        "progress_pct": round(generated / total * 100) if total > 0 else 0,
        "generation_started_at": _format_ts(row[4]),
        "generation_completed_at": _format_ts(row[5]),
        "contact_statuses": status_counts,
    })

from flask import Blueprint, jsonify, request

from ..auth import require_auth, require_role, resolve_tenant
from ..display import display_status, display_tier
from ..models import db, EDIT_REASONS
from ..services.message_generator import regenerate_message, estimate_regeneration_cost

messages_bp = Blueprint("messages", __name__)


@messages_bp.route("/api/messages", methods=["GET"])
@require_auth
def list_messages():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    # Query params
    status = request.args.get("status")
    owner_name = request.args.get("owner_name")
    channel = request.args.get("channel")
    campaign_id = request.args.get("campaign_id")

    where = ["m.tenant_id = :t"]
    params = {"t": tenant_id}

    if status:
        where.append("m.status = :status")
        params["status"] = status
    if channel:
        where.append("m.channel = :channel")
        params["channel"] = channel
    if owner_name:
        where.append("o.name = :owner_name")
        params["owner_name"] = owner_name
    if campaign_id:
        where.append("cc.campaign_id = :campaign_id")
        params["campaign_id"] = campaign_id

    where_clause = " AND ".join(where)

    rows = db.session.execute(
        db.text(f"""
            SELECT
                m.id, m.channel, m.sequence_step, m.variant,
                m.subject, m.body, m.status, m.tone, m.language,
                m.generation_cost_usd, m.review_notes, m.approved_at,
                ct.id AS contact_id, ct.first_name, ct.last_name, ct.job_title,
                ct.linkedin_url, ct.contact_score, ct.icp_fit,
                co.id AS company_id, co.name AS company_name,
                co.tier, co.domain, co.status AS company_status,
                o.name AS owner_name,
                b.name AS tag_name
            FROM messages m
            LEFT JOIN contacts ct ON m.contact_id = ct.id
            LEFT JOIN companies co ON ct.company_id = co.id
            LEFT JOIN owners o ON m.owner_id = o.id
            LEFT JOIN tags b ON m.tag_id = b.id
            LEFT JOIN campaign_contacts cc ON m.campaign_contact_id = cc.id
            WHERE {where_clause}
            ORDER BY ct.contact_score DESC NULLS LAST, m.sequence_step, m.variant
        """),
        params,
    ).fetchall()

    messages = []
    for r in rows:
        messages.append({
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
            "approved_at": r[11].isoformat() if r[11] else None,
            "contact": {
                "id": str(r[12]) if r[12] else None,
                "full_name": ((r[13] or "") + " " + (r[14] or "")).strip(),
                "first_name": r[13],
                "last_name": r[14],
                "job_title": r[15],
                "linkedin_url": r[16],
                "contact_score": r[17],
                "icp_fit": r[18],
                "owner_name": r[24],
                "tag_name": r[25],
            },
            "company": {
                "id": str(r[19]) if r[19] else None,
                "name": r[20],
                "tier": display_tier(r[21]),
                "domain": r[22],
                "status": display_status(r[23]),
            } if r[19] else None,
        })

    return jsonify({"messages": messages})


@messages_bp.route("/api/messages/<message_id>", methods=["PATCH"])
@require_role("editor")
def update_message(message_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    allowed = {"status", "review_notes", "approved_at", "body", "subject",
               "edit_reason", "edit_reason_text"}
    fields = {k: v for k, v in body.items() if k in allowed}

    if not fields:
        return jsonify({"error": "No valid fields to update"}), 400

    # Verify message belongs to tenant
    msg = db.session.execute(
        db.text("""
            SELECT id, body, subject, original_body, original_subject
            FROM messages WHERE id = :id AND tenant_id = :t
        """),
        {"id": message_id, "t": tenant_id},
    ).fetchone()
    if not msg:
        return jsonify({"error": "Message not found"}), 404

    current_body = msg[1]
    current_subject = msg[2]
    existing_original_body = msg[3]
    existing_original_subject = msg[4]

    # If body is being changed, require edit_reason and preserve original
    body_changed = "body" in fields and fields["body"] != current_body
    subject_changed = "subject" in fields and fields["subject"] != current_subject

    if body_changed or subject_changed:
        edit_reason = fields.get("edit_reason")
        if not edit_reason:
            return jsonify({"error": "edit_reason required when changing body or subject"}), 400
        if edit_reason not in EDIT_REASONS:
            return jsonify({"error": f"Invalid edit_reason. Must be one of: {', '.join(EDIT_REASONS)}"}), 400

        # Preserve originals (immutable once set)
        if body_changed and existing_original_body is None:
            fields["original_body"] = current_body
        if subject_changed and existing_original_subject is None:
            fields["original_subject"] = current_subject

    set_parts = []
    params = {"id": message_id, "t": tenant_id}
    safe_columns = {"status", "review_notes", "approved_at", "body", "subject",
                    "edit_reason", "edit_reason_text", "original_body", "original_subject"}
    for k, v in fields.items():
        if k in safe_columns:
            set_parts.append(f"{k} = :{k}")
            params[k] = v

    set_parts.append("updated_at = CURRENT_TIMESTAMP")

    db.session.execute(
        db.text(f"UPDATE messages SET {', '.join(set_parts)} WHERE id = :id AND tenant_id = :t"),
        params,
    )
    db.session.commit()

    return jsonify({"ok": True})


@messages_bp.route("/api/messages/<message_id>/regenerate/estimate", methods=["GET"])
@require_role("editor")
def regen_estimate(message_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    result = estimate_regeneration_cost(message_id, tenant_id)
    if not result:
        return jsonify({"error": "Message not found"}), 404

    return jsonify(result)


@messages_bp.route("/api/messages/<message_id>/regenerate", methods=["POST"])
@require_role("editor")
def regen_message(message_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}

    # Validate formality
    formality = body.get("formality")
    if formality and formality not in ("formal", "informal"):
        return jsonify({"error": "formality must be 'formal' or 'informal'"}), 400

    # Validate instruction length
    instruction = body.get("instruction")
    if instruction and len(instruction) > 200:
        return jsonify({"error": "instruction must be 200 characters or fewer"}), 400

    # Verify message is not currently being generated
    msg_status = db.session.execute(
        db.text("SELECT status FROM messages WHERE id = :id AND tenant_id = :t"),
        {"id": message_id, "t": tenant_id},
    ).fetchone()
    if not msg_status:
        return jsonify({"error": "Message not found"}), 404
    if msg_status[0] == "generating":
        return jsonify({"error": "Cannot regenerate while message is being generated"}), 409

    from flask import g
    user_id = str(g.current_user.id) if hasattr(g, 'current_user') else None

    try:
        result = regenerate_message(
            message_id=message_id,
            tenant_id=tenant_id,
            user_id=user_id,
            language=body.get("language"),
            formality=formality,
            tone=body.get("tone"),
            instruction=instruction,
        )
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Regeneration failed. Please try again."}), 500

    if not result:
        return jsonify({"error": "Message not found"}), 404

    return jsonify(result)


@messages_bp.route("/api/messages/batch", methods=["PATCH"])
@require_role("editor")
def batch_update_messages():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    ids = body.get("ids", [])
    fields = body.get("fields", {})

    if not ids or not fields:
        return jsonify({"error": "ids and fields required"}), 400

    allowed = {"status", "review_notes", "approved_at"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return jsonify({"error": "No valid fields"}), 400

    set_parts = []
    params = {"t": tenant_id, "ids": tuple(ids)}
    for k, v in fields.items():
        set_parts.append(f"{k} = :{k}")
        params[k] = v

    db.session.execute(
        db.text(f"""
            UPDATE messages
            SET {', '.join(set_parts)}
            WHERE tenant_id = :t AND id IN :ids
        """),
        params,
    )
    db.session.commit()

    return jsonify({"ok": True, "updated": len(ids)})

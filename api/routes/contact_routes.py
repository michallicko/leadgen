import json
import math

from flask import Blueprint, jsonify, request

from ..auth import require_auth, require_role, resolve_tenant
from ..display import (
    display_contact_source,
    display_department,
    display_icp_fit,
    display_language,
    display_relationship_status,
    display_seniority,
    display_status,
    display_tier,
)
from ..models import db

contacts_bp = Blueprint("contacts", __name__)


def _iso(v):
    """Safely convert a datetime or string to ISO format."""
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _parse_jsonb(v):
    """Parse a JSONB value that may be a string (SQLite) or dict (Postgres)."""
    if v is None:
        return {}
    if isinstance(v, str):
        return json.loads(v) if v else {}
    return v

ALLOWED_SORT = {
    "last_name", "first_name", "job_title", "email_address", "contact_score",
    "icp_fit", "message_status", "created_at",
}


@contacts_bp.route("/api/contacts", methods=["GET"])
@require_auth
def list_contacts():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    page = max(1, request.args.get("page", 1, type=int))
    page_size = min(100, max(1, request.args.get("page_size", 25, type=int)))
    search = request.args.get("search", "").strip()
    batch_name = request.args.get("batch_name", "").strip()
    owner_name = request.args.get("owner_name", "").strip()
    icp_fit = request.args.get("icp_fit", "").strip()
    message_status = request.args.get("message_status", "").strip()
    company_id = request.args.get("company_id", "").strip()
    sort = request.args.get("sort", "last_name").strip()
    sort_dir = request.args.get("sort_dir", "asc").strip().lower()

    if sort not in ALLOWED_SORT:
        sort = "last_name"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    where = ["ct.tenant_id = :tenant_id"]
    params = {"tenant_id": tenant_id}

    if search:
        where.append(
            "(LOWER(ct.first_name) LIKE LOWER(:search) OR LOWER(ct.last_name) LIKE LOWER(:search)"
            " OR LOWER(ct.email_address) LIKE LOWER(:search)"
            " OR LOWER(ct.job_title) LIKE LOWER(:search))"
        )
        params["search"] = f"%{search}%"
    if batch_name:
        where.append("b.name = :batch_name")
        params["batch_name"] = batch_name
    if owner_name:
        where.append("o.name = :owner_name")
        params["owner_name"] = owner_name
    if icp_fit:
        where.append("ct.icp_fit = :icp_fit")
        params["icp_fit"] = icp_fit
    if message_status:
        where.append("ct.message_status = :message_status")
        params["message_status"] = message_status
    if company_id:
        where.append("ct.company_id = :company_id")
        params["company_id"] = company_id

    # Custom field filters: cf_{key}=value
    cf_idx = 0
    for param_key, param_val in request.args.items():
        if param_key.startswith("cf_") and param_val.strip():
            field_key = param_key[3:]
            # Use json_extract for SQLite compat, ->> for Postgres
            dialect = db.engine.dialect.name
            if dialect == "sqlite":
                where.append(f"json_extract(ct.custom_fields, '$.{field_key}') = :cf_val_{cf_idx}")
            else:
                where.append(f"ct.custom_fields ->> :cf_key_{cf_idx} = :cf_val_{cf_idx}")
                params[f"cf_key_{cf_idx}"] = field_key
            params[f"cf_val_{cf_idx}"] = param_val.strip()
            cf_idx += 1

    where_clause = " AND ".join(where)

    # Count
    total = db.session.execute(
        db.text(f"""
            SELECT COUNT(*)
            FROM contacts ct
            LEFT JOIN batches b ON ct.batch_id = b.id
            LEFT JOIN owners o ON ct.owner_id = o.id
            WHERE {where_clause}
        """),
        params,
    ).scalar() or 0

    pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size

    order = f"ct.{sort} {'ASC' if sort_dir == 'asc' else 'DESC'} NULLS LAST"

    rows = db.session.execute(
        db.text(f"""
            SELECT
                ct.id, ct.first_name, ct.last_name, ct.job_title,
                co.id AS company_id, co.name AS company_name,
                ct.email_address, ct.contact_score, ct.icp_fit,
                ct.message_status,
                o.name AS owner_name, b.name AS batch_name
            FROM contacts ct
            LEFT JOIN companies co ON ct.company_id = co.id
            LEFT JOIN batches b ON ct.batch_id = b.id
            LEFT JOIN owners o ON ct.owner_id = o.id
            WHERE {where_clause}
            ORDER BY {order}
            LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": page_size, "offset": offset},
    ).fetchall()

    contacts = []
    for r in rows:
        first = r[1] or ""
        last = r[2] or ""
        full_name = (first + " " + last).strip() if last else first
        contacts.append({
            "id": str(r[0]),
            "full_name": full_name,
            "first_name": first,
            "last_name": last,
            "job_title": r[3],
            "company_id": str(r[4]) if r[4] else None,
            "company_name": r[5],
            "email_address": r[6],
            "contact_score": r[7],
            "icp_fit": display_icp_fit(r[8]),
            "message_status": r[9],
            "owner_name": r[10],
            "batch_name": r[11],
        })

    return jsonify({
        "contacts": contacts,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    })


@contacts_bp.route("/api/contacts/<contact_id>", methods=["GET"])
@require_auth
def get_contact(contact_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    row = db.session.execute(
        db.text("""
            SELECT
                ct.id, ct.first_name, ct.last_name, ct.job_title,
                ct.email_address, ct.linkedin_url, ct.phone_number,
                ct.profile_photo_url,
                ct.seniority_level, ct.department,
                ct.location_city, ct.location_country,
                ct.icp_fit, ct.relationship_status,
                ct.contact_source, ct.language, ct.message_status,
                ct.ai_champion, ct.ai_champion_score,
                ct.authority_score, ct.contact_score,
                ct.enrichment_cost_usd, ct.processed_enrich,
                ct.email_lookup, ct.duplicity_check,
                ct.duplicity_conflict, ct.duplicity_detail,
                ct.notes, ct.error, ct.custom_fields,
                ct.created_at, ct.updated_at,
                co.id AS company_id, co.name AS company_name,
                co.domain AS company_domain, co.status AS company_status,
                co.tier AS company_tier,
                o.name AS owner_name, b.name AS batch_name
            FROM contacts ct
            LEFT JOIN companies co ON ct.company_id = co.id
            LEFT JOIN owners o ON ct.owner_id = o.id
            LEFT JOIN batches b ON ct.batch_id = b.id
            WHERE ct.id = :id AND ct.tenant_id = :tenant_id
        """),
        {"id": contact_id, "tenant_id": tenant_id},
    ).fetchone()

    if not row:
        return jsonify({"error": "Contact not found"}), 404

    first = row[1] or ""
    last = row[2] or ""
    contact = {
        "id": str(row[0]),
        "first_name": first,
        "last_name": last,
        "full_name": (first + " " + last).strip() if last else first,
        "job_title": row[3],
        "email_address": row[4],
        "linkedin_url": row[5],
        "phone_number": row[6],
        "profile_photo_url": row[7],
        "seniority_level": display_seniority(row[8]),
        "department": display_department(row[9]),
        "location_city": row[10],
        "location_country": row[11],
        "icp_fit": display_icp_fit(row[12]),
        "relationship_status": display_relationship_status(row[13]),
        "contact_source": display_contact_source(row[14]),
        "language": display_language(row[15]),
        "message_status": row[16],
        "ai_champion": row[17],
        "ai_champion_score": row[18],
        "authority_score": row[19],
        "contact_score": row[20],
        "enrichment_cost_usd": float(row[21]) if row[21] is not None else None,
        "processed_enrich": row[22],
        "email_lookup": row[23],
        "duplicity_check": row[24],
        "duplicity_conflict": row[25],
        "duplicity_detail": row[26],
        "notes": row[27],
        "error": row[28],
        "custom_fields": _parse_jsonb(row[29]),
        "created_at": _iso(row[30]),
        "updated_at": _iso(row[31]),
        "company": {
            "id": str(row[32]),
            "name": row[33],
            "domain": row[34],
            "status": display_status(row[35]),
            "tier": display_tier(row[36]),
        } if row[32] else None,
        "owner_name": row[37],
        "batch_name": row[38],
    }

    # Stage completions
    sc_rows = db.session.execute(
        db.text("""
            SELECT stage, status, cost_usd, error, completed_at
            FROM entity_stage_completions
            WHERE entity_id = :id
            ORDER BY completed_at ASC NULLS LAST
        """),
        {"id": contact_id},
    ).fetchall()
    contact["stage_completions"] = [{
        "stage": r[0],
        "status": r[1],
        "cost_usd": float(r[2]) if r[2] is not None else 0,
        "error": r[3],
        "completed_at": _iso(r[4]),
    } for r in sc_rows]

    # Contact enrichment
    enrich_row = db.session.execute(
        db.text("""
            SELECT person_summary, linkedin_profile_summary,
                   relationship_synthesis, enriched_at, enrichment_cost_usd
            FROM contact_enrichment
            WHERE contact_id = :id
        """),
        {"id": contact_id},
    ).fetchone()

    if enrich_row:
        contact["enrichment"] = {
            "person_summary": enrich_row[0],
            "linkedin_profile_summary": enrich_row[1],
            "relationship_synthesis": enrich_row[2],
            "enriched_at": _iso(enrich_row[3]),
            "enrichment_cost_usd": float(enrich_row[4]) if enrich_row[4] is not None else None,
        }
    else:
        contact["enrichment"] = None

    # Messages
    msg_rows = db.session.execute(
        db.text("""
            SELECT m.id, m.channel, m.sequence_step, m.variant,
                   m.subject, m.status, m.tone
            FROM messages m
            WHERE m.contact_id = :id
            ORDER BY m.sequence_step, m.variant
        """),
        {"id": contact_id},
    ).fetchall()
    contact["messages"] = [{
        "id": str(r[0]),
        "channel": r[1],
        "sequence_step": r[2],
        "variant": (r[3] or "a").upper(),
        "subject": r[4],
        "status": r[5],
        "tone": r[6],
    } for r in msg_rows]

    return jsonify(contact)


@contacts_bp.route("/api/contacts/<contact_id>", methods=["PATCH"])
@require_role("editor")
def update_contact(contact_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    allowed = {
        "notes", "icp_fit", "message_status", "relationship_status",
        "seniority_level", "department", "contact_source", "language",
    }
    fields = {k: v for k, v in body.items() if k in allowed}
    custom_fields_update = body.get("custom_fields")

    if not fields and not custom_fields_update:
        return jsonify({"error": "No valid fields to update"}), 400

    row = db.session.execute(
        db.text("SELECT id, custom_fields FROM contacts WHERE id = :id AND tenant_id = :t"),
        {"id": contact_id, "t": tenant_id},
    ).fetchone()
    if not row:
        return jsonify({"error": "Contact not found"}), 404

    set_parts = []
    params = {"id": contact_id}
    for k, v in fields.items():
        set_parts.append(f"{k} = :{k}")
        params[k] = v

    if custom_fields_update and isinstance(custom_fields_update, dict):
        existing_cf = _parse_jsonb(row[1])
        existing_cf.update(custom_fields_update)
        set_parts.append("custom_fields = :custom_fields")
        params["custom_fields"] = json.dumps(existing_cf)

    db.session.execute(
        db.text(f"UPDATE contacts SET {', '.join(set_parts)} WHERE id = :id"),
        params,
    )
    db.session.commit()

    return jsonify({"ok": True})

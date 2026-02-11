from flask import Blueprint, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..display import display_message_status, display_status, display_tier
from ..models import db

batch_bp = Blueprint("batches", __name__)


@batch_bp.route("/api/batches", methods=["GET"])
@require_auth
def list_batches():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    batches = db.session.execute(
        db.text("SELECT name FROM batches WHERE tenant_id = :t AND is_active = true ORDER BY name"),
        {"t": tenant_id},
    ).fetchall()

    owners = db.session.execute(
        db.text("SELECT id, name FROM owners WHERE tenant_id = :t AND is_active = true ORDER BY name"),
        {"t": tenant_id},
    ).fetchall()

    return jsonify({
        "batches": [{"name": r[0]} for r in batches],
        "owners": [{"id": str(r[0]), "name": r[1]} for r in owners],
    })


@batch_bp.route("/api/batch-stats", methods=["POST"])
@require_auth
def batch_stats():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    batch_name = body.get("batch_name", "")
    owner_name = body.get("owner", "")

    if not batch_name:
        return jsonify({"error": "batch_name required"}), 400

    # Resolve batch_id
    batch_row = db.session.execute(
        db.text("SELECT id FROM batches WHERE tenant_id = :t AND name = :n"),
        {"t": tenant_id, "n": batch_name},
    ).fetchone()
    if not batch_row:
        return jsonify({"error": "Batch not found"}), 404
    batch_id = batch_row[0]

    # Resolve owner filter
    owner_id = None
    if owner_name:
        owner_row = db.session.execute(
            db.text("SELECT id FROM owners WHERE tenant_id = :t AND name = :n"),
            {"t": tenant_id, "n": owner_name},
        ).fetchone()
        if owner_row:
            owner_id = owner_row[0]

    # Build WHERE clause for companies
    co_where = "c.tenant_id = :t AND c.batch_id = :b"
    params = {"t": tenant_id, "b": batch_id}
    if owner_id:
        co_where += " AND c.owner_id = :o"
        params["o"] = owner_id

    # Total contacts in batch (with optional owner filter)
    ct_where = "ct.tenant_id = :t AND ct.batch_id = :b"
    ct_params = dict(params)
    if owner_id:
        ct_where += " AND ct.owner_id = :o"

    contacts_total = db.session.execute(
        db.text(f"SELECT COUNT(*) FROM contacts ct WHERE {ct_where}"),
        ct_params,
    ).scalar() or 0

    contacts_unprocessed = db.session.execute(
        db.text(f"SELECT COUNT(*) FROM contacts ct WHERE {ct_where} AND NOT ct.processed_enrich"),
        ct_params,
    ).scalar() or 0

    companies_total = db.session.execute(
        db.text(f"SELECT COUNT(*) FROM companies c WHERE {co_where}"),
        params,
    ).scalar() or 0

    # Status counts
    status_rows = db.session.execute(
        db.text(f"SELECT c.status, COUNT(*) FROM companies c WHERE {co_where} GROUP BY c.status"),
        params,
    ).fetchall()
    status_counts = {}
    for row in status_rows:
        if row[0]:
            status_counts[display_status(row[0])] = row[1]

    # L2 eligible by tier (companies with status = triage_passed)
    tier_rows = db.session.execute(
        db.text(f"""
            SELECT c.tier, COUNT(*)
            FROM companies c
            WHERE {co_where} AND c.status = 'triage_passed'
            GROUP BY c.tier
        """),
        params,
    ).fetchall()
    l2_eligible_by_tier = {}
    for row in tier_rows:
        if row[0]:
            l2_eligible_by_tier[display_tier(row[0])] = row[1]

    # Person eligible: companies with status = enriched_l2
    person_eligible_cos = db.session.execute(
        db.text(f"SELECT COUNT(*) FROM companies c WHERE {co_where} AND c.status = 'enriched_l2'"),
        params,
    ).scalar() or 0

    # Contacts in enriched L2 companies
    contacts_in_enriched = db.session.execute(
        db.text(f"""
            SELECT COUNT(*)
            FROM contacts ct
            JOIN companies c ON ct.company_id = c.id
            WHERE ct.tenant_id = :t AND ct.batch_id = :b AND c.status = 'enriched_l2'
            {"AND ct.owner_id = :o" if owner_id else ""}
        """),
        ct_params,
    ).scalar() or 0

    # Person enriched contacts (processed_enrich = true AND company enriched_l2)
    person_enriched = db.session.execute(
        db.text(f"""
            SELECT COUNT(*)
            FROM contacts ct
            JOIN companies c ON ct.company_id = c.id
            WHERE ct.tenant_id = :t AND ct.batch_id = :b AND c.status = 'enriched_l2'
            AND ct.processed_enrich = true
            {"AND ct.owner_id = :o" if owner_id else ""}
        """),
        ct_params,
    ).scalar() or 0

    # Person failed contacts
    person_failed = db.session.execute(
        db.text(f"""
            SELECT COUNT(*)
            FROM contacts ct
            WHERE ct.tenant_id = :t AND ct.batch_id = :b AND ct.error IS NOT NULL
            {"AND ct.owner_id = :o" if owner_id else ""}
        """),
        ct_params,
    ).scalar() or 0

    # Message status counts
    msg_rows = db.session.execute(
        db.text(f"""
            SELECT ct.message_status, COUNT(*)
            FROM contacts ct
            WHERE ct.tenant_id = :t AND ct.batch_id = :b
            {"AND ct.owner_id = :o" if owner_id else ""}
            AND ct.message_status IS NOT NULL
            GROUP BY ct.message_status
        """),
        ct_params,
    ).fetchall()
    message_status_counts = {}
    for row in msg_rows:
        if row[0]:
            message_status_counts[display_message_status(row[0])] = row[1]

    return jsonify({
        "contacts_total": contacts_total,
        "contacts_unprocessed": contacts_unprocessed,
        "companies_total": companies_total,
        "status_counts": status_counts,
        "l2_eligible_by_tier": l2_eligible_by_tier,
        "person_eligible_companies": person_eligible_cos,
        "person_eligible_contacts": contacts_in_enriched,
        "contacts_in_enriched_cos": contacts_in_enriched,
        "person_enriched_contacts": person_enriched,
        "person_failed_contacts": person_failed,
        "message_status_counts": message_status_counts,
    })

from flask import Blueprint, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..display import display_message_status, display_status, display_tier, tier_db_values
from ..models import CustomFieldDefinition, db

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
        db.text("""
            SELECT DISTINCT u.owner_id, u.display_name
            FROM users u
            JOIN user_tenant_roles utr ON utr.user_id = u.id
            WHERE utr.tenant_id = :t AND u.is_active = true AND u.owner_id IS NOT NULL
            ORDER BY u.display_name
        """),
        {"t": tenant_id},
    ).fetchall()

    custom_defs = CustomFieldDefinition.query.filter_by(
        tenant_id=str(tenant_id), is_active=True,
    ).order_by(CustomFieldDefinition.entity_type, CustomFieldDefinition.display_order).all()

    return jsonify({
        "batches": [{"name": r[0]} for r in batches],
        "owners": [{"id": str(r[0]), "name": r[1]} for r in owners],
        "custom_fields": [d.to_dict() for d in custom_defs],
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
    tier_filter = body.get("tier_filter", [])

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

    # Tier filter — only applied to post-triage queries.
    # Tier is an OUTPUT of L1, so input counts (contacts, companies, pre-L1 statuses) stay unfiltered.
    tier_values = tier_db_values(tier_filter) if tier_filter else []
    tier_sql = ""  # clause for queries that already JOIN companies as c
    tier_co_where = co_where  # tier-filtered company WHERE
    tier_params = dict(params)
    tier_ct_params = dict(ct_params)
    if tier_values:
        tier_ph = ", ".join(f":tier_{i}" for i in range(len(tier_values)))
        tier_sql = f" AND c.tier IN ({tier_ph})"
        tier_co_where = co_where + tier_sql
        for i, tv in enumerate(tier_values):
            tier_params[f"tier_{i}"] = tv
            tier_ct_params[f"tier_{i}"] = tv

    # --- Pre-triage (unfiltered) ---

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

    # Status counts (unfiltered — for pre-L1 statuses: New, Enrichment Failed)
    status_rows = db.session.execute(
        db.text(f"SELECT c.status, COUNT(*) FROM companies c WHERE {co_where} GROUP BY c.status"),
        params,
    ).fetchall()
    status_counts = {}
    for row in status_rows:
        if row[0]:
            status_counts[display_status(row[0])] = row[1]

    # --- Post-triage (tier-filtered) ---

    # Status counts filtered by tier (for Triage: Passed, Disqualified, Enriched L2, etc.)
    status_filtered_rows = db.session.execute(
        db.text(f"SELECT c.status, COUNT(*) FROM companies c WHERE {tier_co_where} GROUP BY c.status"),
        tier_params,
    ).fetchall()
    status_counts_filtered = {}
    for row in status_filtered_rows:
        if row[0]:
            status_counts_filtered[display_status(row[0])] = row[1]

    # L2 eligible by tier (companies with status = triage_passed)
    tier_rows = db.session.execute(
        db.text(f"""
            SELECT c.tier, COUNT(*)
            FROM companies c
            WHERE {tier_co_where} AND c.status = 'triage_passed'
            GROUP BY c.tier
        """),
        tier_params,
    ).fetchall()
    l2_eligible_by_tier = {}
    for row in tier_rows:
        if row[0]:
            l2_eligible_by_tier[display_tier(row[0])] = row[1]

    # Person eligible: companies with status = enriched_l2
    person_eligible_cos = db.session.execute(
        db.text(f"SELECT COUNT(*) FROM companies c WHERE {tier_co_where} AND c.status = 'enriched_l2'"),
        tier_params,
    ).scalar() or 0

    # Contacts in enriched L2 companies
    contacts_in_enriched = db.session.execute(
        db.text(f"""
            SELECT COUNT(*)
            FROM contacts ct
            JOIN companies c ON ct.company_id = c.id
            WHERE ct.tenant_id = :t AND ct.batch_id = :b AND c.status = 'enriched_l2'
            {tier_sql}
            {"AND ct.owner_id = :o" if owner_id else ""}
        """),
        tier_ct_params,
    ).scalar() or 0

    # Person enriched contacts (processed_enrich = true AND company enriched_l2)
    person_enriched = db.session.execute(
        db.text(f"""
            SELECT COUNT(*)
            FROM contacts ct
            JOIN companies c ON ct.company_id = c.id
            WHERE ct.tenant_id = :t AND ct.batch_id = :b AND c.status = 'enriched_l2'
            {tier_sql}
            AND ct.processed_enrich = true
            {"AND ct.owner_id = :o" if owner_id else ""}
        """),
        tier_ct_params,
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
        "status_counts_filtered": status_counts_filtered,
        "l2_eligible_by_tier": l2_eligible_by_tier,
        "person_eligible_companies": person_eligible_cos,
        "person_eligible_contacts": contacts_in_enriched,
        "contacts_in_enriched_cos": contacts_in_enriched,
        "person_enriched_contacts": person_enriched,
        "person_failed_contacts": person_failed,
        "message_status_counts": message_status_counts,
    })

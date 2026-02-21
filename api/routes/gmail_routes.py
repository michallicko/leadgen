"""Gmail import routes: Google Contacts fetch, preview, execute + Gmail scan."""

import json

from flask import Blueprint, g, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import Tag, ImportJob, OAuthConnection, Owner, db
from ..services.dedup import dedup_preview, execute_import
from ..services.google_contacts import fetch_google_contacts, parse_contacts_to_rows

gmail_bp = Blueprint("gmail", __name__)


@gmail_bp.route("/api/gmail/contacts/fetch", methods=["POST"])
@require_auth
def fetch_contacts():
    """Fetch Google Contacts and create an ImportJob.

    Body: { "connection_id": "..." }
    Returns parsed rows ready for preview.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    connection_id = body.get("connection_id")
    if not connection_id:
        return jsonify({"error": "connection_id is required"}), 400

    conn = OAuthConnection.query.filter_by(
        id=connection_id,
        user_id=g.current_user.id,
        tenant_id=str(tenant_id),
        status="active",
    ).first()
    if not conn:
        return jsonify({"error": "Active connection not found"}), 404

    try:
        raw_contacts = fetch_google_contacts(conn)
        parsed_rows = parse_contacts_to_rows(raw_contacts)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch contacts: {str(e)}"}), 500

    # Create import job
    job = ImportJob(
        tenant_id=str(tenant_id),
        user_id=g.current_user.id,
        filename=f"google-contacts-{conn.provider_email}",
        total_rows=len(parsed_rows),
        headers=json.dumps(
            [
                "first_name",
                "last_name",
                "email_address",
                "job_title",
                "phone_number",
                "company_name",
            ]
        ),
        sample_rows=json.dumps(parsed_rows[:5]),
        raw_csv=json.dumps(parsed_rows),
        source="google_contacts",
        oauth_connection_id=connection_id,
        status="mapped",
    )
    db.session.add(job)
    db.session.commit()

    return jsonify(
        {
            "job_id": str(job.id),
            "total_contacts": len(parsed_rows),
            "sample": parsed_rows[:10],
        }
    ), 201


@gmail_bp.route("/api/gmail/contacts/<job_id>/preview", methods=["POST"])
@require_auth
def preview_contacts(job_id):
    """Run dedup preview on fetched Google Contacts."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    job = ImportJob.query.filter_by(
        id=job_id,
        tenant_id=str(tenant_id),
    ).first()
    if not job:
        return jsonify({"error": "Import job not found"}), 404

    raw = job.raw_csv
    parsed_rows = json.loads(raw) if isinstance(raw, str) else raw
    if not parsed_rows:
        return jsonify(
            {
                "job_id": str(job.id),
                "preview_rows": [],
                "total_rows": 0,
                "preview_count": 0,
                "summary": {
                    "new_contacts": 0,
                    "duplicate_contacts": 0,
                    "new_companies": 0,
                    "existing_companies": 0,
                },
            }
        )

    preview_rows = parsed_rows[:25]
    dedup_results = dedup_preview(str(tenant_id), preview_rows)

    new_contacts = sum(1 for r in dedup_results if r["contact_status"] == "new")
    dup_contacts = sum(1 for r in dedup_results if r["contact_status"] == "duplicate")
    new_companies = sum(1 for r in dedup_results if r["company_status"] == "new")
    existing_companies = sum(
        1 for r in dedup_results if r["company_status"] == "existing"
    )

    job.status = "previewed"
    db.session.commit()

    return jsonify(
        {
            "job_id": str(job.id),
            "preview_rows": dedup_results,
            "total_rows": job.total_rows,
            "preview_count": len(dedup_results),
            "summary": {
                "new_contacts": new_contacts,
                "duplicate_contacts": dup_contacts,
                "new_companies": new_companies,
                "existing_companies": existing_companies,
            },
        }
    )


@gmail_bp.route("/api/gmail/contacts/<job_id>/execute", methods=["POST"])
@require_auth
def execute_contacts_import(job_id):
    """Execute import of Google Contacts with dedup strategy.

    Body: { "tag_name": "...", "owner_id": "...", "dedup_strategy": "skip"|"update"|"create_new" }
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    job = ImportJob.query.filter_by(
        id=job_id,
        tenant_id=str(tenant_id),
    ).first()
    if not job:
        return jsonify({"error": "Import job not found"}), 404

    if job.status == "completed":
        return jsonify({"error": "Import already executed"}), 400

    body = request.get_json(silent=True) or {}
    tag_name = body.get("tag_name", "google-contacts-import")
    owner_id = body.get("owner_id")
    strategy = body.get("dedup_strategy", "skip")

    if strategy not in ("skip", "update", "create_new"):
        return jsonify({"error": "Invalid dedup_strategy"}), 400

    if owner_id:
        owner = Owner.query.filter_by(id=owner_id, tenant_id=str(tenant_id)).first()
        if not owner:
            return jsonify({"error": "Owner not found"}), 404

    # Create or find tag
    tag = Tag.query.filter_by(tenant_id=str(tenant_id), name=tag_name).first()
    if not tag:
        tag = Tag(tenant_id=str(tenant_id), name=tag_name, is_active=True)
        db.session.add(tag)
        db.session.flush()

    job.tag_id = str(tag.id)
    job.owner_id = str(owner_id) if owner_id else None
    job.dedup_strategy = strategy
    job.status = "importing"
    db.session.flush()

    try:
        raw = job.raw_csv
        parsed_rows = json.loads(raw) if isinstance(raw, str) else raw

        result = execute_import(
            tenant_id=str(tenant_id),
            parsed_rows=parsed_rows,
            tag_id=tag.id,
            owner_id=owner_id,
            import_job_id=job.id,
            strategy=strategy,
        )

        counts = result["counts"]
        dedup_rows = result["dedup_rows"]

        job.contacts_created = counts["contacts_created"]
        job.contacts_updated = counts["contacts_updated"]
        job.contacts_skipped = counts["contacts_skipped"]
        job.companies_created = counts["companies_created"]
        job.companies_linked = counts["companies_linked"]
        job.dedup_results = json.dumps(
            {
                "summary": {
                    "contacts_created": counts["contacts_created"],
                    "contacts_skipped": counts["contacts_skipped"],
                    "contacts_updated": counts["contacts_updated"],
                },
                "rows": dedup_rows,
            }
        )
        job.status = "completed"
        db.session.commit()

        return jsonify(
            {
                "job_id": str(job.id),
                "status": "completed",
                "tag_name": tag_name,
                "counts": counts,
            }
        )

    except Exception as e:
        db.session.rollback()
        job.status = "error"
        job.error = str(e)
        db.session.commit()
        return jsonify({"error": f"Import failed: {str(e)}"}), 500


# ---- Gmail scan routes ----


@gmail_bp.route("/api/gmail/scan/start", methods=["POST"])
@require_auth
def start_scan():
    """Synchronous Gmail scan — fetches a batch of recent messages, extracts contacts from headers.

    Fast enough for preview (200 messages via batch API). No background thread.

    Body: {
        "connection_id": "...",
        "date_range": 90,           # days (0 = all time)
        "exclude_domains": ["..."],  # optional
        "max_messages": 200          # optional, capped at 500
    }
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    connection_id = body.get("connection_id")
    if not connection_id:
        return jsonify({"error": "connection_id is required"}), 400

    conn = OAuthConnection.query.filter_by(
        id=connection_id,
        user_id=g.current_user.id,
        tenant_id=str(tenant_id),
        status="active",
    ).first()
    if not conn:
        return jsonify({"error": "Active connection not found"}), 404

    config = {
        "date_range": body.get("date_range", 90),
        "exclude_domains": body.get("exclude_domains", []),
        "max_messages": min(body.get("max_messages", 200), 500),
    }

    try:
        from ..services.gmail_scanner import quick_scan

        contacts, messages_scanned = quick_scan(conn, config)
    except Exception as e:
        return jsonify({"error": f"Gmail scan failed: {e}"}), 500

    # Build rows in dedup-compatible format
    rows = []
    for addr, c in contacts.items():
        first_name = c.get("first_name", "") or addr.split("@")[0]
        contact_data = {
            "first_name": first_name,
            "last_name": c.get("last_name", ""),
            "email_address": addr,
            "contact_source": "gmail_scan",
        }
        company_data = {}
        if c.get("domain"):
            company_data["domain"] = c["domain"]
        rows.append({"contact": contact_data, "company": company_data})

    job = ImportJob(
        tenant_id=str(tenant_id),
        user_id=g.current_user.id,
        filename=f"gmail-scan-{conn.provider_email}",
        total_rows=len(rows),
        headers=json.dumps(["first_name", "last_name", "email_address"]),
        raw_csv=json.dumps(rows),
        source="gmail_scan",
        oauth_connection_id=connection_id,
        scan_config=json.dumps(config),
        status="extracted",
    )
    db.session.add(job)
    db.session.commit()

    return jsonify(
        {
            "job_id": str(job.id),
            "status": "extracted",
            "total_contacts": len(rows),
            "messages_scanned": messages_scanned,
        }
    ), 201


@gmail_bp.route("/api/gmail/scan/<job_id>/status", methods=["GET"])
@require_auth
def scan_status(job_id):
    """Get scan progress for a Gmail scan job."""
    from datetime import datetime, timezone

    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    job = ImportJob.query.filter_by(
        id=job_id,
        tenant_id=str(tenant_id),
    ).first()
    if not job:
        return jsonify({"error": "Import job not found"}), 404

    # Detect orphaned scans (thread killed by deploy/restart)
    if job.status == "scanning":
        check_time = job.updated_at or job.created_at
        if check_time:
            age = (
                datetime.now(timezone.utc) - check_time.replace(tzinfo=timezone.utc)
            ).total_seconds()
            if age > 300:  # 5 minutes with no progress update
                job.status = "error"
                job.error = (
                    "Scan timed out (server may have restarted). Please try again."
                )
                db.session.commit()

    progress_raw = job.scan_progress
    progress = (
        json.loads(progress_raw)
        if isinstance(progress_raw, str)
        else (progress_raw or {})
    )

    return jsonify(
        {
            "job_id": str(job.id),
            "status": job.status,
            "scan_progress": progress,
            "error": job.error,
        }
    )

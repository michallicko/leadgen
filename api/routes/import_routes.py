"""Import API routes: upload CSV, AI mapping, preview, execute."""

import csv
import io
import json

from flask import Blueprint, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import Batch, ImportJob, Owner, db
from ..services.csv_mapper import apply_mapping, call_claude_for_mapping
from ..services.dedup import dedup_preview, execute_import

imports_bp = Blueprint("imports", __name__)

MAX_CSV_SIZE = 10 * 1024 * 1024  # 10 MB


def _parse_csv_text(text):
    """Parse CSV text, return (headers, rows) where rows are list of dicts."""
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    rows = list(reader)
    return headers, rows


@imports_bp.route("/api/imports/upload", methods=["POST"])
@require_auth
def upload_csv():
    """Accept CSV file, parse headers + sample rows, call Claude for mapping.

    Expects multipart form with 'file' field.
    Returns import job with AI-generated column mapping.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    user = request.environ.get("user") or getattr(request, "_user", None)
    from flask import g
    user_id = g.current_user.id

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only CSV files are supported"}), 400

    raw = file.read()
    if len(raw) > MAX_CSV_SIZE:
        return jsonify({"error": f"File too large (max {MAX_CSV_SIZE // (1024*1024)} MB)"}), 400

    # Try UTF-8 first, fall back to latin-1
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    headers, rows = _parse_csv_text(text)
    if not headers:
        return jsonify({"error": "Could not parse CSV headers"}), 400

    sample_rows = []
    for row in rows[:5]:
        sample_rows.append({h: row.get(h, "") for h in headers})

    # Call Claude for AI column mapping
    try:
        mapping_result = call_claude_for_mapping(headers, sample_rows)
    except Exception as e:
        mapping_result = {
            "mappings": [],
            "warnings": [f"AI mapping failed: {str(e)}. Manual mapping required."],
            "combine_columns": [],
        }

    # Compute overall confidence
    confidences = [m.get("confidence", 0) for m in mapping_result.get("mappings", [])
                   if m.get("target")]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    # Create import job
    job = ImportJob(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        filename=file.filename,
        file_size_bytes=len(raw),
        total_rows=len(rows),
        headers=json.dumps(headers) if isinstance(headers, list) else headers,
        sample_rows=json.dumps(sample_rows) if isinstance(sample_rows, list) else sample_rows,
        raw_csv=text,
        column_mapping=json.dumps(mapping_result) if isinstance(mapping_result, dict) else mapping_result,
        mapping_confidence=round(avg_confidence, 2),
        status="mapped",
    )
    db.session.add(job)
    db.session.commit()

    return jsonify({
        "job_id": str(job.id),
        "filename": file.filename,
        "total_rows": len(rows),
        "headers": headers,
        "sample_rows": sample_rows,
        "mapping": mapping_result,
        "mapping_confidence": round(avg_confidence, 2),
    }), 201


@imports_bp.route("/api/imports/<job_id>/preview", methods=["POST"])
@require_auth
def preview_import(job_id):
    """Accept user-adjusted mapping, return parsed rows with dedup results.

    Body: { "mapping": <adjusted mapping object> }
    Returns first 25 rows with dedup status.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    job = ImportJob.query.filter_by(id=job_id, tenant_id=str(tenant_id)).first()
    if not job:
        return jsonify({"error": "Import job not found"}), 404

    body = request.get_json(silent=True) or {}
    mapping = body.get("mapping")
    if mapping:
        job.column_mapping = json.dumps(mapping) if isinstance(mapping, dict) else mapping
        db.session.flush()
    else:
        mapping = json.loads(job.column_mapping) if isinstance(job.column_mapping, str) else job.column_mapping

    # Parse all rows
    headers, all_rows = _parse_csv_text(job.raw_csv)

    # Apply mapping to first 25 rows for preview
    preview_rows = all_rows[:25]
    parsed = [apply_mapping(row, mapping) for row in preview_rows]

    # Run dedup preview
    dedup_results = dedup_preview(str(tenant_id), parsed)

    # Summary counts
    new_contacts = sum(1 for r in dedup_results if r["contact_status"] == "new")
    dup_contacts = sum(1 for r in dedup_results if r["contact_status"] == "duplicate")
    new_companies = sum(1 for r in dedup_results if r["company_status"] == "new")
    existing_companies = sum(1 for r in dedup_results if r["company_status"] == "existing")

    job.status = "previewed"
    db.session.commit()

    return jsonify({
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
    })


@imports_bp.route("/api/imports/<job_id>/execute", methods=["POST"])
@require_auth
def execute_import_job(job_id):
    """Create batch, insert companies/contacts, run dedup.

    Body: { "batch_name": "...", "owner_id": "...", "dedup_strategy": "skip"|"update"|"create_new" }
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    job = ImportJob.query.filter_by(id=job_id, tenant_id=str(tenant_id)).first()
    if not job:
        return jsonify({"error": "Import job not found"}), 404

    if job.status == "completed":
        return jsonify({"error": "Import already executed"}), 400

    body = request.get_json(silent=True) or {}
    batch_name = body.get("batch_name", f"import-{job.filename}")
    owner_id = body.get("owner_id")
    strategy = body.get("dedup_strategy", "skip")

    if strategy not in ("skip", "update", "create_new"):
        return jsonify({"error": "Invalid dedup_strategy"}), 400

    # Validate owner if provided
    if owner_id:
        owner = Owner.query.filter_by(id=owner_id, tenant_id=str(tenant_id)).first()
        if not owner:
            return jsonify({"error": "Owner not found"}), 404

    # Create or find batch
    batch = Batch.query.filter_by(tenant_id=str(tenant_id), name=batch_name).first()
    if not batch:
        batch = Batch(tenant_id=str(tenant_id), name=batch_name, is_active=True)
        db.session.add(batch)
        db.session.flush()

    job.batch_id = str(batch.id)
    job.owner_id = str(owner_id) if owner_id else None
    job.dedup_strategy = strategy
    job.status = "importing"
    db.session.flush()

    try:
        # Parse all rows and apply mapping
        mapping = json.loads(job.column_mapping) if isinstance(job.column_mapping, str) else job.column_mapping
        _headers, all_rows = _parse_csv_text(job.raw_csv)
        parsed = [apply_mapping(row, mapping) for row in all_rows]

        # Execute import
        counts = execute_import(
            tenant_id=str(tenant_id),
            parsed_rows=parsed,
            batch_id=batch.id,
            owner_id=owner_id,
            import_job_id=job.id,
            strategy=strategy,
        )

        job.contacts_created = counts["contacts_created"]
        job.contacts_updated = counts["contacts_updated"]
        job.contacts_skipped = counts["contacts_skipped"]
        job.companies_created = counts["companies_created"]
        job.companies_linked = counts["companies_linked"]
        job.status = "completed"
        db.session.commit()

        return jsonify({
            "job_id": str(job.id),
            "status": "completed",
            "batch_name": batch_name,
            "counts": counts,
        })

    except Exception as e:
        db.session.rollback()
        job.status = "error"
        job.error = str(e)
        db.session.commit()
        return jsonify({"error": f"Import failed: {str(e)}"}), 500


@imports_bp.route("/api/imports/<job_id>/status", methods=["GET"])
@require_auth
def import_status(job_id):
    """Get import job status."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    job = ImportJob.query.filter_by(id=job_id, tenant_id=str(tenant_id)).first()
    if not job:
        return jsonify({"error": "Import job not found"}), 404

    return jsonify(job.to_dict())


@imports_bp.route("/api/imports", methods=["GET"])
@require_auth
def list_imports():
    """List past import jobs for tenant."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    jobs = ImportJob.query.filter_by(
        tenant_id=str(tenant_id),
    ).order_by(ImportJob.created_at.desc()).limit(50).all()

    return jsonify({
        "imports": [j.to_dict() for j in jobs],
    })

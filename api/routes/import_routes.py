"""Import API routes: upload CSV, AI mapping, preview, execute."""

import csv
import io
import json

from flask import Blueprint, jsonify, request
from openpyxl import load_workbook

from ..auth import require_auth, resolve_tenant
from ..models import Tag, CustomFieldDefinition, ImportJob, Owner, db
from ..services.csv_mapper import apply_mapping, call_claude_for_mapping
from ..services.dedup import dedup_preview, execute_import
from ..services.llm_logger import log_llm_usage

imports_bp = Blueprint("imports", __name__)

MAX_CSV_SIZE = 10 * 1024 * 1024  # 10 MB


def _auto_create_custom_field_defs(tenant_id, mapping):
    """Scan mapping for custom.* targets and auto-create missing definitions.

    Also checks suggested_custom_field on mappings and creates definitions for those.
    """
    needed = {}  # (entity_type, field_key) → field_label

    for m in mapping.get("mappings", []):
        target = m.get("target")
        if target:
            # e.g. "contact.custom.email_secondary"
            parts = target.split(".", 2)
            if len(parts) == 3 and parts[1] == "custom":
                entity_type, _, field_key = parts
                # Prefer user-edited label from suggested_custom_field, fall back to csv_header
                suggestion = m.get("suggested_custom_field") or {}
                label = suggestion.get("field_label") or m.get(
                    "csv_header", field_key.replace("_", " ").title()
                )
                field_type = suggestion.get("field_type", "text")
                needed[(entity_type, field_key)] = {
                    "label": label,
                    "field_type": field_type,
                }

    for (entity_type, field_key), info in needed.items():
        existing = CustomFieldDefinition.query.filter_by(
            tenant_id=tenant_id,
            entity_type=entity_type,
            field_key=field_key,
        ).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
            continue
        cfd = CustomFieldDefinition(
            tenant_id=tenant_id,
            entity_type=entity_type,
            field_key=field_key,
            field_label=info["label"],
            field_type=info["field_type"],
        )
        db.session.add(cfd)

    if needed:
        db.session.flush()


def _parse_csv_text(text):
    """Parse CSV text, return (headers, rows) where rows are list of dicts."""
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    rows = list(reader)
    return headers, rows


def _parse_xlsx_bytes(raw):
    """Parse XLSX bytes (first sheet), return (headers, rows) where rows are list of dicts."""
    wb = load_workbook(filename=io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    header_row = next(rows_iter, None)
    if not header_row:
        wb.close()
        return [], []
    headers = [str(h) if h is not None else "" for h in header_row]
    rows = []
    for row in rows_iter:
        rows.append(
            {headers[i]: (str(v) if v is not None else "") for i, v in enumerate(row)}
        )
    wb.close()
    return headers, rows


def _rows_to_csv_text(headers, rows):
    """Convert headers + list-of-dicts to CSV text for storage."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


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

    from flask import g

    user_id = g.current_user.id

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".csv") or filename_lower.endswith(".xlsx")):
        return jsonify({"error": "Only CSV and XLSX files are supported"}), 400

    raw = file.read()
    if len(raw) > MAX_CSV_SIZE:
        return jsonify(
            {"error": f"File too large (max {MAX_CSV_SIZE // (1024 * 1024)} MB)"}
        ), 400

    if filename_lower.endswith(".xlsx"):
        headers, rows = _parse_xlsx_bytes(raw)
        text = _rows_to_csv_text(headers, rows)
    else:
        # Try UTF-8 first, fall back to latin-1
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        headers, rows = _parse_csv_text(text)

    if not headers:
        return jsonify({"error": "Could not parse file headers"}), 400

    sample_rows = []
    for row in rows[:5]:
        sample_rows.append({h: row.get(h, "") for h in headers})

    # Fetch existing custom field definitions for AI context
    custom_defs_rows = CustomFieldDefinition.query.filter_by(
        tenant_id=str(tenant_id),
        is_active=True,
    ).all()
    custom_defs = [d.to_dict() for d in custom_defs_rows]

    # Call Claude for AI column mapping
    usage_info = None
    try:
        mapping_result, usage_info = call_claude_for_mapping(
            headers, sample_rows, custom_defs=custom_defs
        )
    except Exception as e:
        mapping_result = {
            "mappings": [],
            "warnings": [f"AI mapping failed: {str(e)}. Manual mapping required."],
            "combine_columns": [],
        }

    # Compute overall confidence
    confidences = [
        m.get("confidence", 0)
        for m in mapping_result.get("mappings", [])
        if m.get("target")
    ]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    # Create import job
    job = ImportJob(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        filename=file.filename,
        file_size_bytes=len(raw),
        total_rows=len(rows),
        headers=json.dumps(headers) if isinstance(headers, list) else headers,
        sample_rows=json.dumps(sample_rows)
        if isinstance(sample_rows, list)
        else sample_rows,
        raw_csv=text,
        column_mapping=json.dumps(mapping_result)
        if isinstance(mapping_result, dict)
        else mapping_result,
        mapping_confidence=round(avg_confidence, 2),
        status="mapped",
    )
    db.session.add(job)
    db.session.flush()

    # Log LLM usage if we got usage info from Claude
    if usage_info:
        log_llm_usage(
            tenant_id=str(tenant_id),
            operation="csv_column_mapping",
            model=usage_info["model"],
            input_tokens=usage_info["input_tokens"],
            output_tokens=usage_info["output_tokens"],
            user_id=str(user_id),
            duration_ms=usage_info.get("duration_ms"),
            metadata={
                "import_job_id": str(job.id),
                "filename": file.filename,
                "headers_count": len(headers),
            },
        )

    db.session.commit()

    return jsonify(
        {
            "job_id": str(job.id),
            "filename": file.filename,
            "total_rows": len(rows),
            "headers": headers,
            "sample_rows": sample_rows,
            "mapping": mapping_result,
            "mapping_confidence": round(avg_confidence, 2),
        }
    ), 201


@imports_bp.route("/api/imports/<job_id>/remap", methods=["POST"])
@require_auth
def remap_import(job_id):
    """Re-run AI column mapping on an existing import job's CSV data.

    Uses the current prompt (with custom field support) to generate fresh suggestions.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    job = ImportJob.query.filter_by(id=job_id, tenant_id=str(tenant_id)).first()
    if not job:
        return jsonify({"error": "Import job not found"}), 404

    if job.status == "completed":
        return jsonify({"error": "Cannot remap a completed import"}), 400

    headers, rows = _parse_csv_text(job.raw_csv)
    if not headers:
        return jsonify({"error": "Could not parse stored CSV"}), 400

    sample_rows = [{h: row.get(h, "") for h in headers} for row in rows[:5]]

    custom_defs_rows = CustomFieldDefinition.query.filter_by(
        tenant_id=str(tenant_id),
        is_active=True,
    ).all()
    custom_defs = [d.to_dict() for d in custom_defs_rows]

    try:
        mapping_result, usage_info = call_claude_for_mapping(
            headers, sample_rows, custom_defs=custom_defs
        )
    except Exception as e:
        return jsonify({"error": f"AI mapping failed: {str(e)}"}), 500

    confidences = [
        m.get("confidence", 0)
        for m in mapping_result.get("mappings", [])
        if m.get("target")
    ]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    job.column_mapping = json.dumps(mapping_result)
    job.mapping_confidence = round(avg_confidence, 2)
    job.status = "mapped"
    db.session.flush()

    if usage_info:
        from flask import g

        log_llm_usage(
            tenant_id=str(tenant_id),
            operation="csv_column_remap",
            model=usage_info["model"],
            input_tokens=usage_info["input_tokens"],
            output_tokens=usage_info["output_tokens"],
            user_id=str(g.current_user.id),
            duration_ms=usage_info.get("duration_ms"),
            metadata={
                "import_job_id": str(job.id),
                "filename": job.filename,
                "headers_count": len(headers),
            },
        )

    db.session.commit()

    return jsonify(
        {
            "job_id": str(job.id),
            "filename": job.filename,
            "total_rows": job.total_rows,
            "headers": headers,
            "sample_rows": sample_rows,
            "mapping": mapping_result,
            "mapping_confidence": round(avg_confidence, 2),
        }
    )


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
        job.column_mapping = (
            json.dumps(mapping) if isinstance(mapping, dict) else mapping
        )
        db.session.flush()
    else:
        mapping = (
            json.loads(job.column_mapping)
            if isinstance(job.column_mapping, str)
            else job.column_mapping
        )

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


@imports_bp.route("/api/imports/<job_id>/execute", methods=["POST"])
@require_auth
def execute_import_job(job_id):
    """Create tag, insert companies/contacts, run dedup.

    Body: { "tag_name": "...", "owner_id": "...", "dedup_strategy": "skip"|"update"|"create_new" }
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
    tag_name = body.get("tag_name", f"import-{job.filename}")
    owner_id = body.get("owner_id")
    strategy = body.get("dedup_strategy", "skip")

    if strategy not in ("skip", "update", "create_new"):
        return jsonify({"error": "Invalid dedup_strategy"}), 400

    # Validate owner if provided
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
        # Parse all rows and apply mapping
        mapping = (
            json.loads(job.column_mapping)
            if isinstance(job.column_mapping, str)
            else job.column_mapping
        )

        # Auto-create custom field definitions for any custom.* targets
        _auto_create_custom_field_defs(str(tenant_id), mapping)

        _headers, all_rows = _parse_csv_text(job.raw_csv)
        parsed = [apply_mapping(row, mapping) for row in all_rows]

        # Execute import
        result = execute_import(
            tenant_id=str(tenant_id),
            parsed_rows=parsed,
            tag_id=tag.id,
            owner_id=owner_id,
            import_job_id=job.id,
            strategy=strategy,
        )

        counts = result["counts"]
        dedup_rows = result["dedup_rows"]
        total_conflicts = sum(len(r.get("conflicts", [])) for r in dedup_rows)

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
                    "total_conflicts": total_conflicts,
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


@imports_bp.route("/api/imports/<job_id>/results", methods=["GET"])
@require_auth
def import_results(job_id):
    """Get detailed dedup results for a completed import.

    Query params:
      filter: all|created|skipped|updated|conflicts (default: all)
      page: 1-based page number (default: 1)
    Returns summary + paginated rows.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    job = ImportJob.query.filter_by(id=job_id, tenant_id=str(tenant_id)).first()
    if not job:
        return jsonify({"error": "Import job not found"}), 404

    if job.status != "completed":
        return jsonify({"error": "Import not yet completed"}), 400

    raw = job.dedup_results
    if isinstance(raw, str):
        dedup_data = json.loads(raw) if raw else {}
    else:
        dedup_data = raw or {}

    summary = dedup_data.get("summary", {})
    all_rows = dedup_data.get("rows", [])

    filter_type = request.args.get("filter", "all")
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50

    if filter_type == "created":
        filtered = [r for r in all_rows if r.get("action") == "created"]
    elif filter_type == "skipped":
        filtered = [r for r in all_rows if r.get("action") == "skipped"]
    elif filter_type == "updated":
        filtered = [r for r in all_rows if r.get("action") == "updated"]
    elif filter_type == "conflicts":
        filtered = [r for r in all_rows if r.get("conflicts")]
    else:
        filtered = all_rows

    total = len(filtered)
    start = (page - 1) * per_page
    page_rows = filtered[start : start + per_page]

    return jsonify(
        {
            "job_id": str(job.id),
            "summary": summary,
            "filter": filter_type,
            "page": page,
            "per_page": per_page,
            "total": total,
            "rows": page_rows,
        }
    )


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

    include_data = job.status in ("uploaded", "mapped", "previewed")
    return jsonify(job.to_dict(include_data=include_data))


@imports_bp.route("/api/imports", methods=["GET"])
@require_auth
def list_imports():
    """List past import jobs for tenant."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    jobs = (
        ImportJob.query.filter_by(
            tenant_id=str(tenant_id),
        )
        .order_by(ImportJob.created_at.desc())
        .limit(50)
        .all()
    )

    return jsonify(
        {
            "imports": [j.to_dict() for j in jobs],
        }
    )

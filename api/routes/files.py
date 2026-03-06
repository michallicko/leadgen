"""File upload and management routes.

Endpoints:
  POST   /api/files/upload     Upload a file for processing
  GET    /api/files             List uploaded files for tenant
  GET    /api/files/<id>        Get file metadata + extraction status
  GET    /api/files/<id>/content Get extracted content
  DELETE /api/files/<id>        Delete file and extracted content
  POST   /api/files/from-url    Fetch and process content from a URL
"""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import FileUpload, db
from ..services.multimodal.ingestion import (
    create_file_record,
    fetch_url_content,
    process_file,
    resolve_mime_type,
    store_file,
    validate_upload,
)

logger = logging.getLogger(__name__)

files_bp = Blueprint("files", __name__)


@files_bp.route("/api/files/upload", methods=["POST"])
@require_auth
def upload_file():
    """Upload a file for content extraction and analysis."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    user_id = str(g.token_payload["sub"])

    if "file" not in request.files:
        return jsonify({"error": "No file provided. Use 'file' field."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No filename provided."}), 400

    # Read file data
    file_data = file.read()
    size_bytes = len(file_data)
    mime_type = resolve_mime_type(file.filename, file.content_type or "")

    # Validate
    error = validate_upload(file.filename, size_bytes, mime_type)
    if error:
        if "too large" in error.lower():
            return jsonify({"error": error}), 413
        if "empty" in error.lower():
            return jsonify({"error": error}), 400
        return jsonify({"error": error}), 415

    try:
        # Store file
        storage_path = store_file(file_data, file.filename, str(tenant_id))

        # Create DB record
        file_record = create_file_record(
            tenant_id=str(tenant_id),
            user_id=user_id,
            original_filename=file.filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
        )
        db.session.commit()

        # Process file (extract + summarize)
        file_id = str(file_record.id)
        process_file(file_id)

        # Refresh to get updated status
        db.session.refresh(file_record)

        return jsonify(file_record.to_dict(include_content=True)), 201

    except Exception:
        db.session.rollback()
        logger.exception("File upload failed")
        return jsonify({"error": "File upload failed."}), 500


@files_bp.route("/api/files", methods=["GET"])
@require_auth
def list_files():
    """List uploaded files for the current tenant."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    files = (
        FileUpload.query.filter_by(tenant_id=str(tenant_id))
        .order_by(FileUpload.created_at.desc())
        .limit(100)
        .all()
    )

    return jsonify({"files": [f.to_dict() for f in files]})


@files_bp.route("/api/files/<file_id>", methods=["GET"])
@require_auth
def get_file(file_id):
    """Get file metadata and extraction status."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    file_record = FileUpload.query.filter_by(
        id=file_id, tenant_id=str(tenant_id)
    ).first()
    if not file_record:
        return jsonify({"error": "File not found."}), 404

    return jsonify(file_record.to_dict(include_content=True))


@files_bp.route("/api/files/<file_id>/content", methods=["GET"])
@require_auth
def get_file_content(file_id):
    """Get extracted content from a file.

    Query params:
      detail: 'summary' (default) or 'full'
    """
    from ..services.multimodal.context_manager import get_file_context

    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    file_record = FileUpload.query.filter_by(
        id=file_id, tenant_id=str(tenant_id)
    ).first()
    if not file_record:
        return jsonify({"error": "File not found."}), 404

    if file_record.processing_status != "completed":
        return jsonify(
            {
                "error": "File is still {}.".format(file_record.processing_status),
                "status": file_record.processing_status,
            }
        ), 202

    level = "l2" if request.args.get("detail") == "full" else "l1"
    result = get_file_context(file_id, level)

    if not result:
        return jsonify({"error": "No content available."}), 404

    return jsonify(
        {
            "file_id": file_id,
            "filename": file_record.original_filename,
            "detail_level": result["level"],
            "content": result["content"],
            "tokens": result["tokens"],
        }
    )


@files_bp.route("/api/files/<file_id>", methods=["DELETE"])
@require_auth
def delete_file(file_id):
    """Delete a file and its extracted content."""
    import os

    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    file_record = FileUpload.query.filter_by(
        id=file_id, tenant_id=str(tenant_id)
    ).first()
    if not file_record:
        return jsonify({"error": "File not found."}), 404

    # Delete physical file
    try:
        if os.path.exists(file_record.storage_path):
            os.remove(file_record.storage_path)
    except OSError:
        logger.warning("Failed to delete file: %s", file_record.storage_path)

    # Delete DB records (cascades to extracted_content)
    db.session.delete(file_record)
    db.session.commit()

    return jsonify({"message": "File deleted.", "id": file_id})


@files_bp.route("/api/files/from-url", methods=["POST"])
@require_auth
def upload_from_url():
    """Fetch content from a URL and process it.

    Body: {"url": "https://example.com/page"}
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    user_id = str(g.token_payload["sub"])

    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "URL is required."}), 400

    if not url.startswith(("http://", "https://")):
        return jsonify(
            {"error": "Invalid URL. Must start with http:// or https://"}
        ), 400

    # Fetch URL content
    result = fetch_url_content(url)
    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    file_data = result["data"]
    mime_type = resolve_mime_type(result["filename"], result["mime_type"])
    size_bytes = len(file_data)

    # Validate
    error = validate_upload(result["filename"], size_bytes, mime_type)
    if error:
        return jsonify({"error": error}), 415

    try:
        storage_path = store_file(file_data, result["filename"], str(tenant_id))

        file_record = create_file_record(
            tenant_id=str(tenant_id),
            user_id=user_id,
            original_filename=url[:255],  # Use URL as filename
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
        )
        db.session.commit()

        file_id = str(file_record.id)
        process_file(file_id)

        db.session.refresh(file_record)

        return jsonify(file_record.to_dict(include_content=True)), 201

    except Exception:
        db.session.rollback()
        logger.exception("URL processing failed")
        return jsonify({"error": "Failed to process URL content."}), 500

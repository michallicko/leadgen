"""Version history API routes for strategy documents (BL-1014)."""

import logging

from flask import Blueprint, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import StrategyDocument
from ..services.version_service import (
    create_version,
    get_version,
    list_versions,
    restore_version,
)

logger = logging.getLogger(__name__)

version_bp = Blueprint("versions", __name__)


def _get_doc_for_tenant(document_id: str, tenant_id: str):
    """Validate document belongs to tenant."""
    doc = StrategyDocument.query.get(document_id)
    if not doc or doc.tenant_id != tenant_id:
        return None
    return doc


@version_bp.route("/api/playbook/<document_id>/versions", methods=["GET"])
@require_auth
def get_versions(document_id):
    """List all versions for a strategy document."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = _get_doc_for_tenant(document_id, tenant_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    limit = request.args.get("limit", 50, type=int)
    versions = list_versions(document_id, limit=limit)
    return jsonify(versions)


@version_bp.route("/api/playbook/<document_id>/versions", methods=["POST"])
@require_auth
def create_manual_version(document_id):
    """Create a manual version snapshot."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = _get_doc_for_tenant(document_id, tenant_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    data = request.get_json(silent=True) or {}
    content = data.get("content", doc.content or "")
    description = data.get("description", "Manual save")

    version = create_version(
        document_id=document_id,
        content=content,
        author_type="user",
        description=description,
    )
    return jsonify(version), 201


@version_bp.route("/api/playbook/<document_id>/versions/<version_id>", methods=["GET"])
@require_auth
def get_version_detail(document_id, version_id):
    """Get full version content."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = _get_doc_for_tenant(document_id, tenant_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    version = get_version(version_id)
    if not version or version.get("document_id") != document_id:
        return jsonify({"error": "Version not found"}), 404

    return jsonify(version)


@version_bp.route(
    "/api/playbook/<document_id>/versions/<version_id>/restore", methods=["POST"]
)
@require_auth
def restore_version_endpoint(document_id, version_id):
    """Restore a previous version."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = _get_doc_for_tenant(document_id, tenant_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    try:
        result = restore_version(document_id, version_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify(result)

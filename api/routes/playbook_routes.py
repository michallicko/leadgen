"""Playbook (GTM Strategy) API routes."""
from flask import Blueprint, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import StrategyDocument, db

playbook_bp = Blueprint("playbook", __name__)


@playbook_bp.route("/api/playbook", methods=["GET"])
@require_auth
def get_playbook():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        doc = StrategyDocument(tenant_id=tenant_id, status="draft")
        db.session.add(doc)
        db.session.commit()

    return jsonify(doc.to_dict()), 200


@playbook_bp.route("/api/playbook", methods=["PUT"])
@require_auth
def update_playbook():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}

    if "version" not in data:
        return jsonify({"error": "version is required"}), 400

    content = data.get("content", {})
    version = data["version"]
    status = data.get("status")

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    if doc.version != version:
        return jsonify({
            "error": "Conflict: document was edited by someone else",
            "current_version": doc.version,
            "updated_by": doc.updated_by,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }), 409

    doc.content = content
    doc.version = doc.version + 1
    doc.updated_by = getattr(request, "user_id", None)
    if status:
        doc.status = status

    db.session.commit()
    return jsonify(doc.to_dict()), 200

"""Playbook (GTM Strategy) API routes."""
from flask import Blueprint, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import StrategyDocument, StrategyChatMessage, db

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


def _get_or_create_document(tenant_id):
    """Return the tenant's strategy document, creating one if needed."""
    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        doc = StrategyDocument(tenant_id=tenant_id, status="draft")
        db.session.add(doc)
        db.session.flush()
    return doc


@playbook_bp.route("/api/playbook/chat", methods=["GET"])
@require_auth
def get_chat_history():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    limit = min(request.args.get("limit", 50, type=int), 200)

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"messages": []}), 200

    messages = (
        StrategyChatMessage.query
        .filter_by(document_id=doc.id)
        .order_by(StrategyChatMessage.created_at.asc())
        .limit(limit)
        .all()
    )

    return jsonify({"messages": [m.to_dict() for m in messages]}), 200


@playbook_bp.route("/api/playbook/chat", methods=["POST"])
@require_auth
def post_chat_message():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    message_text = data.get("message")
    if not message_text:
        return jsonify({"error": "message is required"}), 400

    doc = _get_or_create_document(tenant_id)
    user_id = getattr(request, "user_id", None)

    user_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc.id,
        role="user",
        content=message_text,
        created_by=user_id,
    )
    db.session.add(user_msg)
    db.session.flush()

    assistant_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc.id,
        role="assistant",
        content="I'm a placeholder. LLM integration coming in Task 7.",
    )
    db.session.add(assistant_msg)
    db.session.commit()

    return jsonify({
        "user_message": user_msg.to_dict(),
        "assistant_message": assistant_msg.to_dict(),
    }), 201

"""Playbook (GTM Strategy) API routes."""
import json
import logging
import os
import re

from flask import Blueprint, Response, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import StrategyDocument, StrategyChatMessage, Tenant, db
from ..services.anthropic_client import AnthropicClient
from ..services.playbook_service import build_extraction_prompt, build_messages, build_system_prompt

logger = logging.getLogger(__name__)

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


@playbook_bp.route("/api/playbook/extract", methods=["POST"])
@require_auth
def extract_strategy():
    """Extract structured data from the strategy document using an LLM."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    doc = StrategyDocument.query.filter_by(tenant_id=tenant_id).first()
    if not doc:
        return jsonify({"error": "No strategy document found"}), 404

    system_prompt, user_prompt = build_extraction_prompt(doc.content or {})

    client = _get_anthropic_client()

    try:
        result = client.query(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4096,
            temperature=0.1,
        )
        raw_text = result.content
    except Exception as e:
        logger.exception("LLM extraction error: %s", e)
        return jsonify({"error": "LLM extraction failed: {}".format(str(e))}), 502

    # Strip markdown code fences if the LLM wraps the JSON
    stripped = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', raw_text, flags=re.DOTALL)

    try:
        extracted_data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("LLM returned invalid JSON: %s", raw_text[:200])
        return jsonify({
            "error": "Failed to parse extraction result as JSON",
            "detail": str(e),
        }), 422

    doc.extracted_data = extracted_data
    db.session.commit()

    return jsonify({
        "extracted_data": extracted_data,
        "version": doc.version,
    }), 200


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


def _wants_streaming(req):
    """Check if the client wants an SSE streaming response."""
    accept = req.headers.get("Accept", "")
    if "text/event-stream" in accept:
        return True
    if req.args.get("stream", "").lower() in ("true", "1", "yes"):
        return True
    return False


def _get_anthropic_client():
    """Create an AnthropicClient with the API key from environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    return AnthropicClient(api_key=api_key)


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
    tenant = db.session.get(Tenant, tenant_id)
    user_id = getattr(request, "user_id", None)

    # Save the user message before any LLM work
    user_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc.id,
        role="user",
        content=message_text,
        created_by=user_id,
    )
    db.session.add(user_msg)
    db.session.flush()

    # Load chat history for context
    history = (
        StrategyChatMessage.query
        .filter_by(document_id=doc.id)
        .filter(StrategyChatMessage.id != user_msg.id)
        .order_by(StrategyChatMessage.created_at.asc())
        .all()
    )

    # Build prompt and messages
    system_prompt = build_system_prompt(tenant, doc)
    messages = build_messages(history, message_text)

    client = _get_anthropic_client()

    if _wants_streaming(request):
        return _stream_response(
            client, system_prompt, messages,
            tenant_id, doc.id, user_msg,
        )
    else:
        return _sync_response(
            client, system_prompt, messages,
            tenant_id, doc.id, user_msg,
        )


def _stream_response(client, system_prompt, messages, tenant_id, doc_id, user_msg):
    """Return an SSE streaming response with LLM chunks.

    DB operations (saving the assistant message) happen inside the generator
    using the app context, since the generator runs outside the request context.
    """
    # Capture the app for use inside the generator (runs outside request context)
    from flask import current_app
    app = current_app._get_current_object()

    def generate():
        full_text = []

        try:
            for chunk in client.stream_query(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=4096,
                temperature=0.4,
            ):
                full_text.append(chunk)
                yield "data: {}\n\n".format(
                    json.dumps({"type": "chunk", "text": chunk})
                )
        except Exception as e:
            logger.exception("LLM streaming error: %s", e)
            yield "data: {}\n\n".format(
                json.dumps({"type": "error", "message": str(e)})
            )
            return

        # Save the assistant message after streaming completes
        assistant_content = "".join(full_text)
        with app.app_context():
            assistant_msg = StrategyChatMessage(
                tenant_id=tenant_id,
                document_id=doc_id,
                role="assistant",
                content=assistant_content,
            )
            db.session.add(assistant_msg)
            db.session.commit()
            msg_id = assistant_msg.id

        yield "data: {}\n\n".format(
            json.dumps({"type": "done", "message_id": msg_id})
        )

    # Commit the user message before entering the generator
    db.session.commit()

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sync_response(client, system_prompt, messages, tenant_id, doc_id, user_msg):
    """Return a non-streaming JSON response with the full LLM reply."""
    try:
        full_text = []
        for chunk in client.stream_query(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=4096,
            temperature=0.4,
        ):
            full_text.append(chunk)

        assistant_content = "".join(full_text)
    except Exception as e:
        logger.exception("LLM query error: %s", e)
        # Fall back to error message so the user message is still saved
        assistant_content = "Sorry, I encountered an error generating a response. Please try again."

    assistant_msg = StrategyChatMessage(
        tenant_id=tenant_id,
        document_id=doc_id,
        role="assistant",
        content=assistant_content,
    )
    db.session.add(assistant_msg)
    db.session.commit()

    return jsonify({
        "user_message": user_msg.to_dict(),
        "assistant_message": assistant_msg.to_dict(),
    }), 201

"""Strategy template API routes.

CRUD for GTM strategy templates + AI-assisted template application.
"""

import json
import logging
import os

from flask import Blueprint, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import (
    StrategyDocument,
    StrategyTemplate,
    db,
)
from ..services.anthropic_client import AnthropicClient
from ..services.llm_logger import log_llm_usage

try:
    from ..services.budget import BudgetExceededError, check_budget, consume_credits

    _HAS_BUDGET = True
except ImportError:
    _HAS_BUDGET = False

logger = logging.getLogger(__name__)

strategy_templates_bp = Blueprint("strategy_templates", __name__)


# Estimated credits for a template merge (used for budget pre-check)
_TEMPLATE_MERGE_ESTIMATED_CREDITS = 50


# ---------------------------------------------------------------------------
# GET /api/strategy-templates  — list templates
# ---------------------------------------------------------------------------


@strategy_templates_bp.route("/api/strategy-templates", methods=["GET"])
@require_auth
def list_strategy_templates():
    """List available templates: system (tenant_id IS NULL) + tenant-owned."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    templates = StrategyTemplate.query.filter(
        db.or_(
            StrategyTemplate.tenant_id == str(tenant_id),
            StrategyTemplate.is_system.is_(True),
        )
    ).order_by(
        StrategyTemplate.is_system.desc(),
        StrategyTemplate.created_at.desc(),
    ).all()

    result = []
    for t in templates:
        d = t.to_dict()
        d["section_headers"] = t.section_headers
        result.append(d)

    return jsonify(result), 200


# ---------------------------------------------------------------------------
# GET /api/strategy-templates/<id>  — get single template with content
# ---------------------------------------------------------------------------


@strategy_templates_bp.route("/api/strategy-templates/<template_id>", methods=["GET"])
@require_auth
def get_strategy_template(template_id):
    """Get a single template with full content."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    template = StrategyTemplate.query.get(template_id)
    if not template:
        return jsonify({"error": "Template not found"}), 404

    # Access check: system templates are readable by all; tenant templates by their owner
    if not template.is_system and str(template.tenant_id) != str(tenant_id):
        return jsonify({"error": "Template not found"}), 404

    d = template.to_dict(include_content=True)
    d["section_headers"] = template.section_headers
    return jsonify(d), 200


# ---------------------------------------------------------------------------
# POST /api/strategy-templates  — create template from current strategy
# ---------------------------------------------------------------------------


@strategy_templates_bp.route("/api/strategy-templates", methods=["POST"])
@require_auth
def create_strategy_template():
    """Create a user template from the current strategy document."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400

    description = data.get("description", "").strip() or None
    category = data.get("category", "").strip() or None

    # Load current strategy document for content
    doc = StrategyDocument.query.filter_by(tenant_id=str(tenant_id)).first()
    if not doc or not doc.content:
        return jsonify({"error": "No strategy document to save as template"}), 400

    template = StrategyTemplate(
        tenant_id=str(tenant_id),
        name=name,
        description=description,
        category=category,
        content_template=doc.content,
        extracted_data_template=doc.extracted_data or {},
        is_system=False,
    )
    db.session.add(template)
    db.session.commit()

    result = template.to_dict(include_content=True)
    result["section_headers"] = template.section_headers
    return jsonify(result), 201


# ---------------------------------------------------------------------------
# PATCH /api/strategy-templates/<id>  — update name/description
# ---------------------------------------------------------------------------


@strategy_templates_bp.route(
    "/api/strategy-templates/<template_id>", methods=["PATCH"]
)
@require_auth
def update_strategy_template(template_id):
    """Update a user template's name or description."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    template = StrategyTemplate.query.get(template_id)
    if not template:
        return jsonify({"error": "Template not found"}), 404

    if template.is_system:
        return jsonify({"error": "Cannot modify system templates"}), 403

    if str(template.tenant_id) != str(tenant_id):
        return jsonify({"error": "Template not found"}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = data["name"].strip()
        if not name:
            return jsonify({"error": "Name cannot be empty"}), 400
        template.name = name
    if "description" in data:
        template.description = data["description"].strip() or None

    template.updated_at = db.func.now()
    db.session.commit()
    return jsonify(template.to_dict()), 200


# ---------------------------------------------------------------------------
# DELETE /api/strategy-templates/<id>  — delete user template
# ---------------------------------------------------------------------------


@strategy_templates_bp.route(
    "/api/strategy-templates/<template_id>", methods=["DELETE"]
)
@require_auth
def delete_strategy_template(template_id):
    """Delete a tenant-owned template. Cannot delete system templates."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    template = StrategyTemplate.query.get(template_id)
    if not template:
        return jsonify({"error": "Template not found"}), 404

    if template.is_system:
        return jsonify({"error": "Cannot delete system templates"}), 403

    if str(template.tenant_id) != str(tenant_id):
        return jsonify({"error": "Template not found"}), 404

    db.session.delete(template)
    db.session.commit()
    return jsonify({"success": True}), 200


# ---------------------------------------------------------------------------
# POST /api/playbook/apply-template  — AI-merge template + context
# ---------------------------------------------------------------------------


@strategy_templates_bp.route("/api/playbook/apply-template", methods=["POST"])
@require_auth
def apply_template():
    """Apply a strategy template with AI-assisted merge.

    1. Load template content + user's onboarding context
    2. Budget check
    3. Call Claude to merge template + context → personalized strategy
    4. Snapshot current doc (for undo), save merged content
    5. Return updated document
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    template_id = data.get("template_id")
    if not template_id:
        return jsonify({"error": "template_id is required"}), 400

    # Load template
    template = StrategyTemplate.query.get(template_id)
    if not template:
        return jsonify({"error": "Template not found"}), 404

    # Access check
    if not template.is_system and str(template.tenant_id) != str(tenant_id):
        return jsonify({"error": "Template not found"}), 404

    # Load or create strategy document
    doc = StrategyDocument.query.filter_by(tenant_id=str(tenant_id)).first()
    if not doc:
        doc = StrategyDocument(tenant_id=str(tenant_id), status="draft")
        db.session.add(doc)
        db.session.flush()

    # Budget check (when budget service is available)
    if _HAS_BUDGET:
        try:
            check_budget(tenant_id, _TEMPLATE_MERGE_ESTIMATED_CREDITS)
        except BudgetExceededError as e:
            return jsonify({
                "error": "Token budget exceeded",
                "code": "budget_exceeded",
                "details": {
                    "remaining": e.remaining,
                    "required": e.required,
                },
            }), 402

    # Gather context for AI merge
    context_parts = []
    if doc.objective:
        context_parts.append(f"Business Objective: {doc.objective}")
    if doc.extracted_data:
        ed = doc.extracted_data if isinstance(doc.extracted_data, dict) else {}
        if ed:
            context_parts.append(
                f"Existing Strategy Data: {json.dumps(ed, indent=2)}"
            )

    context_text = "\n".join(context_parts) if context_parts else "No additional context available."

    # Build prompt
    system_prompt = (
        "You are a GTM strategy consultant. You are given a strategy template "
        "and the user's business context. Your job is to merge them into a "
        "personalized GTM strategy document.\n\n"
        "Rules:\n"
        "- Preserve the template's section structure (all H2 headings must appear)\n"
        "- Replace all {{placeholder}} tokens with specific, relevant content\n"
        "- Adapt the strategy to the user's industry, geography, and objectives\n"
        "- Use concrete, actionable language — no generic filler\n"
        "- Output pure Markdown — no code fences, no preamble, no commentary\n"
        "- If context is missing for a placeholder, use sensible defaults "
        "and mark them with [CUSTOMIZE] so the user knows to update them"
    )

    user_prompt = (
        f"## Template: {template.name}\n\n"
        f"{template.content_template}\n\n"
        f"---\n\n"
        f"## User Context\n\n"
        f"{context_text}\n\n"
        f"---\n\n"
        f"Merge the template above with the user context to produce a "
        f"complete, personalized GTM strategy document. "
        f"Output only the final Markdown document."
    )

    # Call Claude
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "AI service not configured"}), 503

    try:
        client = AnthropicClient(api_key=api_key)
        response = client.query(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
        )
    except Exception:
        logger.exception("Template merge failed")
        return jsonify({"error": "AI merge failed. Please try again."}), 500

    # Log LLM usage
    log_llm_usage(
        tenant_id=str(tenant_id),
        user_id=getattr(request, "user_id", None),
        provider="anthropic",
        model=response.model,
        operation="template_merge",
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=float(response.cost_usd),
    )

    # Consume credits (when budget service is available)
    if _HAS_BUDGET:
        actual_credits = response.input_tokens + response.output_tokens
        consume_credits(tenant_id, actual_credits)

    # Snapshot current doc state for undo
    from ..services.strategy_tools import _snapshot

    _snapshot(doc, edit_source="template_apply")

    # Apply merged content
    doc.content = response.content
    doc.version += 1
    doc.updated_by = getattr(request, "user_id", None)
    doc.updated_at = db.func.now()

    # Also merge extracted_data_template as defaults
    if template.extracted_data_template:
        edt = template.extracted_data_template
        if isinstance(edt, str):
            try:
                edt = json.loads(edt)
            except (json.JSONDecodeError, TypeError):
                edt = {}
        if edt and isinstance(edt, dict):
            current_ed = doc.extracted_data or {}
            if isinstance(current_ed, str):
                try:
                    current_ed = json.loads(current_ed)
                except (json.JSONDecodeError, TypeError):
                    current_ed = {}
            # Merge: template defaults, user's existing data takes precedence
            merged = {**edt, **current_ed}
            doc.extracted_data = merged

    db.session.commit()

    result = doc.to_dict()
    result["has_ai_edits"] = True
    result["applied_template"] = template.name
    return jsonify(result), 200

"""Custom field definition CRUD routes."""

import re

from flask import Blueprint, jsonify, request

from ..auth import require_auth, require_role, resolve_tenant
from ..models import CustomFieldDefinition, db

custom_fields_bp = Blueprint("custom_fields", __name__)

VALID_ENTITY_TYPES = {"contact", "company"}
VALID_FIELD_TYPES = {"text", "number", "url", "email", "date", "select"}


def _slugify(label):
    """Convert a display label to a snake_case field key."""
    key = label.strip().lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)
    key = key.strip("_")
    return key


@custom_fields_bp.route("/api/custom-fields", methods=["GET"])
@require_auth
def list_custom_fields():
    """List active custom field definitions for the tenant.

    Query params: entity_type (optional, 'contact' or 'company')
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    query = CustomFieldDefinition.query.filter_by(
        tenant_id=str(tenant_id),
        is_active=True,
    )
    entity_type = request.args.get("entity_type", "").strip()
    if entity_type and entity_type in VALID_ENTITY_TYPES:
        query = query.filter_by(entity_type=entity_type)

    defs = query.order_by(
        CustomFieldDefinition.entity_type,
        CustomFieldDefinition.display_order,
        CustomFieldDefinition.field_label,
    ).all()

    return jsonify({"custom_fields": [d.to_dict() for d in defs]})


@custom_fields_bp.route("/api/custom-fields", methods=["POST"])
@require_role("editor")
def create_custom_field():
    """Create a new custom field definition.

    Body: { entity_type, field_label, field_type?, options?, display_order? }
    Auto-generates field_key from field_label.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    body = request.get_json(silent=True) or {}
    entity_type = (body.get("entity_type") or "").strip()
    field_label = (body.get("field_label") or "").strip()
    field_type = (body.get("field_type") or "text").strip()
    options = body.get("options", [])
    display_order = body.get("display_order", 0)

    if entity_type not in VALID_ENTITY_TYPES:
        return jsonify(
            {"error": f"entity_type must be one of: {', '.join(VALID_ENTITY_TYPES)}"}
        ), 400
    if not field_label:
        return jsonify({"error": "field_label is required"}), 400
    if field_type not in VALID_FIELD_TYPES:
        return jsonify(
            {"error": f"field_type must be one of: {', '.join(VALID_FIELD_TYPES)}"}
        ), 400

    field_key = body.get("field_key") or _slugify(field_label)
    if not field_key:
        return jsonify({"error": "Could not generate field_key from label"}), 400

    # Check for conflicts
    existing = CustomFieldDefinition.query.filter_by(
        tenant_id=str(tenant_id),
        entity_type=entity_type,
        field_key=field_key,
    ).first()
    if existing:
        if existing.is_active:
            return jsonify(
                {"error": f"Field key '{field_key}' already exists for {entity_type}"}
            ), 409
        # Re-activate soft-deleted field
        existing.field_label = field_label
        existing.field_type = field_type
        existing.options = options
        existing.display_order = display_order
        existing.is_active = True
        db.session.commit()
        return jsonify(existing.to_dict()), 200

    cfd = CustomFieldDefinition(
        tenant_id=str(tenant_id),
        entity_type=entity_type,
        field_key=field_key,
        field_label=field_label,
        field_type=field_type,
        options=options,
        display_order=display_order,
    )
    db.session.add(cfd)
    db.session.commit()

    return jsonify(cfd.to_dict()), 201


@custom_fields_bp.route("/api/custom-fields/<field_id>", methods=["PUT"])
@require_role("editor")
def update_custom_field(field_id):
    """Update a custom field definition (label, type, options, display_order)."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    cfd = CustomFieldDefinition.query.filter_by(
        id=field_id,
        tenant_id=str(tenant_id),
    ).first()
    if not cfd:
        return jsonify({"error": "Custom field not found"}), 404

    body = request.get_json(silent=True) or {}

    if "field_label" in body:
        cfd.field_label = body["field_label"].strip()
    if "field_type" in body:
        ft = body["field_type"].strip()
        if ft not in VALID_FIELD_TYPES:
            return jsonify(
                {"error": f"field_type must be one of: {', '.join(VALID_FIELD_TYPES)}"}
            ), 400
        cfd.field_type = ft
    if "options" in body:
        cfd.options = body["options"]
    if "display_order" in body:
        cfd.display_order = body["display_order"]

    db.session.commit()
    return jsonify(cfd.to_dict())


@custom_fields_bp.route("/api/custom-fields/<field_id>", methods=["DELETE"])
@require_role("editor")
def delete_custom_field(field_id):
    """Soft-delete a custom field definition (set is_active=false)."""
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    cfd = CustomFieldDefinition.query.filter_by(
        id=field_id,
        tenant_id=str(tenant_id),
    ).first()
    if not cfd:
        return jsonify({"error": "Custom field not found"}), 404

    cfd.is_active = False
    db.session.commit()
    return jsonify({"ok": True})

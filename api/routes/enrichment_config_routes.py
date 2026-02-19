"""API routes for enrichment configuration templates and schedules."""
import json

from flask import Blueprint, jsonify, request

from ..auth import require_auth, resolve_tenant
from ..models import EnrichmentConfig, EnrichmentSchedule, db

enrichment_config_bp = Blueprint("enrichment_configs", __name__)


# ---------------------------------------------------------------------------
# Enrichment Config CRUD
# ---------------------------------------------------------------------------

@enrichment_config_bp.route("/api/enrichment-configs", methods=["POST"])
@require_auth
def create_config():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    # If setting as default, clear existing defaults
    if data.get("is_default"):
        EnrichmentConfig.query.filter_by(
            tenant_id=tenant_id, is_default=True
        ).update({"is_default": False})

    config_val = data.get("config", {})
    if isinstance(config_val, dict):
        config_val = json.dumps(config_val)

    ec = EnrichmentConfig(
        tenant_id=tenant_id,
        name=data["name"],
        description=data.get("description", ""),
        config=config_val,
        is_default=bool(data.get("is_default", False)),
        created_by=getattr(request, "user_id", None),
    )
    db.session.add(ec)
    db.session.commit()
    return jsonify(ec.to_dict()), 201


@enrichment_config_bp.route("/api/enrichment-configs", methods=["GET"])
@require_auth
def list_configs():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    configs = EnrichmentConfig.query.filter_by(
        tenant_id=tenant_id
    ).order_by(EnrichmentConfig.created_at.desc()).all()
    return jsonify([c.to_dict() for c in configs]), 200


@enrichment_config_bp.route("/api/enrichment-configs/<config_id>", methods=["GET"])
@require_auth
def get_config(config_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    ec = EnrichmentConfig.query.filter_by(
        id=config_id, tenant_id=tenant_id
    ).first()
    if not ec:
        return jsonify({"error": "not found"}), 404
    return jsonify(ec.to_dict()), 200


@enrichment_config_bp.route("/api/enrichment-configs/<config_id>", methods=["PATCH"])
@require_auth
def update_config(config_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    ec = EnrichmentConfig.query.filter_by(
        id=config_id, tenant_id=tenant_id
    ).first()
    if not ec:
        return jsonify({"error": "not found"}), 404

    data = request.get_json(silent=True) or {}

    if "name" in data:
        ec.name = data["name"]
    if "description" in data:
        ec.description = data["description"]
    if "config" in data:
        config_val = data["config"]
        if isinstance(config_val, dict):
            config_val = json.dumps(config_val)
        ec.config = config_val
    if "is_default" in data and data["is_default"]:
        EnrichmentConfig.query.filter(
            EnrichmentConfig.tenant_id == tenant_id,
            EnrichmentConfig.id != config_id,
            EnrichmentConfig.is_default == True,  # noqa: E712
        ).update({"is_default": False})
        ec.is_default = True
    elif "is_default" in data:
        ec.is_default = False

    db.session.commit()
    return jsonify(ec.to_dict()), 200


@enrichment_config_bp.route("/api/enrichment-configs/<config_id>", methods=["DELETE"])
@require_auth
def delete_config(config_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    ec = EnrichmentConfig.query.filter_by(
        id=config_id, tenant_id=tenant_id
    ).first()
    if not ec:
        return jsonify({"error": "not found"}), 404
    db.session.delete(ec)
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# Enrichment Schedule CRUD
# ---------------------------------------------------------------------------

@enrichment_config_bp.route("/api/enrichment-schedules", methods=["POST"])
@require_auth
def create_schedule():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True) or {}
    if not data.get("config_id"):
        return jsonify({"error": "config_id is required"}), 400
    if not data.get("schedule_type"):
        return jsonify({"error": "schedule_type is required"}), 400

    valid_types = {"cron", "on_new_entity"}
    if data["schedule_type"] not in valid_types:
        return jsonify({"error": f"schedule_type must be one of {valid_types}"}), 400

    ec = EnrichmentConfig.query.filter_by(
        id=data["config_id"], tenant_id=tenant_id
    ).first()
    if not ec:
        return jsonify({"error": "config not found"}), 404

    sched = EnrichmentSchedule(
        tenant_id=tenant_id,
        config_id=data["config_id"],
        schedule_type=data["schedule_type"],
        cron_expression=data.get("cron_expression"),
        tag_filter=data.get("tag_filter"),
        is_active=data.get("is_active", True),
    )
    db.session.add(sched)
    db.session.commit()
    return jsonify(sched.to_dict()), 201


@enrichment_config_bp.route("/api/enrichment-schedules", methods=["GET"])
@require_auth
def list_schedules():
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    schedules = EnrichmentSchedule.query.filter_by(
        tenant_id=tenant_id
    ).order_by(EnrichmentSchedule.created_at.desc()).all()
    return jsonify([s.to_dict() for s in schedules]), 200


@enrichment_config_bp.route("/api/enrichment-schedules/<schedule_id>", methods=["PATCH"])
@require_auth
def update_schedule(schedule_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    sched = EnrichmentSchedule.query.filter_by(
        id=schedule_id, tenant_id=tenant_id
    ).first()
    if not sched:
        return jsonify({"error": "not found"}), 404

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        sched.is_active = bool(data["is_active"])
    if "cron_expression" in data:
        sched.cron_expression = data["cron_expression"]
    if "tag_filter" in data:
        sched.tag_filter = data["tag_filter"]

    db.session.commit()
    return jsonify(sched.to_dict()), 200


@enrichment_config_bp.route("/api/enrichment-schedules/<schedule_id>", methods=["DELETE"])
@require_auth
def delete_schedule(schedule_id):
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    sched = EnrichmentSchedule.query.filter_by(
        id=schedule_id, tenant_id=tenant_id
    ).first()
    if not sched:
        return jsonify({"error": "not found"}), 404
    db.session.delete(sched)
    db.session.commit()
    return "", 204

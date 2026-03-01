import json
import re
import secrets

from flask import Blueprint, g, jsonify, request

from ..auth import hash_password, require_auth, require_role, resolve_tenant
from ..models import (
    Campaign,
    Contact,
    StrategyDocument,
    Tenant,
    User,
    UserTenantRole,
    db,
)

tenants_bp = Blueprint("tenants", __name__, url_prefix="/api/tenants")

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")


def _parse_settings(tenant):
    """Parse tenant settings, handling SQLite text or PG JSONB."""
    settings = tenant.settings
    if isinstance(settings, str):
        settings = json.loads(settings) if settings else {}
    return settings or {}


def _has_tenant_access(user, tenant_id):
    """Check if user is super_admin or has a role on the given tenant."""
    if user.is_super_admin:
        return True
    return any(r.tenant_id == tenant_id for r in user.roles)


def _is_tenant_admin(user, tenant_id):
    """Check if user is super_admin or admin on the given tenant."""
    if user.is_super_admin:
        return True
    return any(r.tenant_id == tenant_id and r.role == "admin" for r in user.roles)


@tenants_bp.route("", methods=["GET"])
@require_auth
def list_tenants():
    user = g.current_user

    if user.is_super_admin:
        tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    else:
        tenant_ids = [r.tenant_id for r in user.roles]
        tenants = (
            Tenant.query.filter(Tenant.id.in_(tenant_ids))
            .order_by(Tenant.created_at.desc())
            .all()
        )

    return jsonify([t.to_dict() for t in tenants])


@tenants_bp.route("", methods=["POST"])
@require_role("admin")
def create_tenant():
    user = g.current_user
    if not user.is_super_admin:
        return jsonify({"error": "Only super admins can create namespaces"}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or "").strip().lower()
    domain = (data.get("domain") or "").strip() or None
    admin_email = (data.get("admin_email") or "").strip().lower() or None

    if not name or not slug:
        return jsonify({"error": "name and slug required"}), 400

    if len(slug) < 2 or not SLUG_RE.match(slug):
        return jsonify(
            {"error": "Slug must be 2+ chars, lowercase alphanumeric and hyphens only"}
        ), 400

    if Tenant.query.filter_by(slug=slug).first():
        return jsonify({"error": "Slug already taken"}), 409

    tenant = Tenant(
        name=name, slug=slug, domain=domain, settings=data.get("settings", {})
    )
    db.session.add(tenant)
    db.session.flush()

    result = tenant.to_dict()
    temp_password = None

    if admin_email:
        existing_user = User.query.filter_by(email=admin_email).first()
        if existing_user:
            utr = UserTenantRole(
                user_id=existing_user.id,
                tenant_id=tenant.id,
                role="admin",
                granted_by=user.id,
            )
            db.session.add(utr)
        else:
            temp_password = secrets.token_urlsafe(12)
            new_user = User(
                email=admin_email,
                password_hash=hash_password(temp_password),
                display_name=admin_email.split("@")[0],
            )
            db.session.add(new_user)
            db.session.flush()
            utr = UserTenantRole(
                user_id=new_user.id,
                tenant_id=tenant.id,
                role="admin",
                granted_by=user.id,
            )
            db.session.add(utr)

    db.session.commit()

    if temp_password:
        result["temp_password"] = temp_password

    return jsonify(result), 201


@tenants_bp.route("/<tenant_id>", methods=["GET"])
@require_auth
def get_tenant(tenant_id):
    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    if not _has_tenant_access(g.current_user, tenant_id):
        return jsonify({"error": "Insufficient permissions"}), 403

    return jsonify(tenant.to_dict())


@tenants_bp.route("/<tenant_id>", methods=["PUT"])
@require_role("admin")
def update_tenant(tenant_id):
    if not g.current_user.is_super_admin:
        return jsonify({"error": "Only super admins can update namespaces"}), 403

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    if "name" in data:
        tenant.name = data["name"]
    if "domain" in data:
        tenant.domain = data["domain"] or None
    if "settings" in data:
        tenant.settings = data["settings"]
    if "is_active" in data:
        tenant.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify(tenant.to_dict())


@tenants_bp.route("/<tenant_id>", methods=["DELETE"])
@require_role("admin")
def deactivate_tenant(tenant_id):
    if not g.current_user.is_super_admin:
        return jsonify({"error": "Only super admins can deactivate namespaces"}), 403

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    tenant.is_active = False
    db.session.commit()
    return jsonify({"ok": True, "message": "Namespace deactivated"})


@tenants_bp.route("/<tenant_id>/settings", methods=["PATCH"])
@require_role("admin")
def patch_tenant_settings(tenant_id):
    """Merge-patch tenant settings (e.g. language, enrichment_language, onboarding)."""
    from ..services.language import VALID_LANGUAGE_CODES

    if not _is_tenant_admin(g.current_user, tenant_id):
        return jsonify({"error": "Insufficient permissions"}), 403

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Validate language fields
    for key in ("language", "enrichment_language"):
        if key in data:
            val = data[key]
            if val is not None and val not in VALID_LANGUAGE_CODES:
                return jsonify({"error": f"Invalid {key}: {val}"}), 400

    # Allowed settings keys for merge-patch
    ALLOWED_KEYS = (
        "language",
        "enrichment_language",
        "onboarding_path",
        "checklist_dismissed",
    )

    # Merge-patch: update existing settings dict
    current = _parse_settings(tenant)
    for key in ALLOWED_KEYS:
        if key in data:
            if data[key] is None:
                current.pop(key, None)
            else:
                current[key] = data[key]

    tenant.settings = current
    db.session.commit()
    return jsonify(tenant.to_dict())


@tenants_bp.route("/<tenant_id>/users", methods=["GET"])
@require_auth
def list_tenant_users(tenant_id):
    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    if not _is_tenant_admin(g.current_user, tenant_id):
        return jsonify({"error": "Insufficient permissions"}), 403

    roles = (
        UserTenantRole.query.filter_by(tenant_id=tenant_id)
        .join(User, UserTenantRole.user_id == User.id)
        .order_by(User.display_name)
        .all()
    )

    result = []
    for r in roles:
        u = r.user
        result.append(
            {
                "id": str(u.id),
                "email": u.email,
                "display_name": u.display_name,
                "is_active": u.is_active,
                "role": r.role,
                "granted_at": r.granted_at.isoformat() if r.granted_at else None,
            }
        )

    return jsonify(result)


@tenants_bp.route("/onboarding-status", methods=["GET"])
@require_auth
def get_onboarding_status():
    """Return data counts and onboarding settings for the current namespace.

    Used by the frontend to decide whether to show the entry signpost,
    context-aware empty states, and the progress checklist.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    # Count entities
    contact_count = Contact.query.filter_by(tenant_id=tenant_id).count()
    campaign_count = Campaign.query.filter_by(tenant_id=tenant_id).count()

    # Check if a strategy document exists with content
    strategy_doc = StrategyDocument.query.filter_by(
        tenant_id=tenant_id
    ).first()
    has_strategy = bool(
        strategy_doc
        and strategy_doc.content
        and strategy_doc.content.strip()
    )

    settings = _parse_settings(tenant)

    return jsonify(
        {
            "contact_count": contact_count,
            "campaign_count": campaign_count,
            "has_strategy": has_strategy,
            "onboarding_path": settings.get("onboarding_path"),
            "checklist_dismissed": settings.get("checklist_dismissed", False),
        }
    )


VALID_ONBOARDING_PATHS = {"strategy", "import", "templates"}


@tenants_bp.route("/onboarding-settings", methods=["PATCH"])
@require_auth
def patch_onboarding_settings():
    """Update onboarding-specific settings for the current namespace.

    Any authenticated user with namespace access can update these.
    Only allows onboarding_path and checklist_dismissed keys.
    """
    tenant_id = resolve_tenant()
    if not tenant_id:
        return jsonify({"error": "Tenant not found"}), 404

    if not _has_tenant_access(g.current_user, tenant_id):
        return jsonify({"error": "Insufficient permissions"}), 403

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    current = _parse_settings(tenant)

    if "onboarding_path" in data:
        val = data["onboarding_path"]
        if val is not None and val not in VALID_ONBOARDING_PATHS:
            return jsonify(
                {"error": f"Invalid onboarding_path: {val}"}
            ), 400
        if val is None:
            current.pop("onboarding_path", None)
        else:
            current["onboarding_path"] = val

    if "checklist_dismissed" in data:
        val = data["checklist_dismissed"]
        if not isinstance(val, bool):
            return jsonify(
                {"error": "checklist_dismissed must be a boolean"}
            ), 400
        current["checklist_dismissed"] = val

    tenant.settings = current
    db.session.commit()
    return jsonify(
        {
            "onboarding_path": current.get("onboarding_path"),
            "checklist_dismissed": current.get("checklist_dismissed", False),
        }
    )

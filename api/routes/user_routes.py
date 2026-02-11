from flask import Blueprint, g, jsonify, request

from ..auth import hash_password, require_role, verify_password
from ..models import Tenant, User, UserTenantRole, db

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


@users_bp.route("", methods=["GET"])
@require_role("admin")
def list_users():
    user = g.current_user
    tenant_id = request.args.get("tenant_id")

    if tenant_id:
        users = (
            User.query.join(UserTenantRole, UserTenantRole.user_id == User.id)
            .filter(UserTenantRole.tenant_id == tenant_id)
            .order_by(User.created_at.desc())
            .all()
        )
    elif user.is_super_admin:
        users = User.query.order_by(User.created_at.desc()).all()
    else:
        tenant_ids = [r.tenant_id for r in user.roles]
        users = (
            User.query.join(UserTenantRole, UserTenantRole.user_id == User.id)
            .filter(UserTenantRole.tenant_id.in_(tenant_ids))
            .order_by(User.created_at.desc())
            .all()
        )

    return jsonify([u.to_dict(include_roles=True) for u in users])


@users_bp.route("", methods=["POST"])
@require_role("admin")
def create_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip()
    tenant_id = data.get("tenant_id")
    role = data.get("role", "viewer")

    if not email or not password or not display_name:
        return jsonify({"error": "email, password, and display_name required"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if role not in ("admin", "editor", "viewer"):
        return jsonify({"error": "Invalid role"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        owner_id=data.get("owner_id"),
    )
    db.session.add(user)
    db.session.flush()

    if tenant_id:
        tenant = db.session.get(Tenant, tenant_id)
        if not tenant:
            db.session.rollback()
            return jsonify({"error": "Tenant not found"}), 404

        utr = UserTenantRole(
            user_id=user.id,
            tenant_id=tenant_id,
            role=role,
            granted_by=g.current_user.id,
        )
        db.session.add(utr)

    db.session.commit()
    return jsonify(user.to_dict(include_roles=True)), 201


@users_bp.route("/<user_id>", methods=["PUT"])
@require_role("admin")
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    if "display_name" in data:
        user.display_name = data["display_name"]

    if "is_active" in data:
        user.is_active = bool(data["is_active"])

    if "owner_id" in data:
        user.owner_id = data["owner_id"] or None

    if "tenant_id" in data and "role" in data:
        tenant_id = data["tenant_id"]
        role = data["role"]
        if role not in ("admin", "editor", "viewer"):
            return jsonify({"error": "Invalid role"}), 400

        current = g.current_user
        if not current.is_super_admin:
            is_admin_on_tenant = any(
                r.tenant_id == tenant_id and r.role == "admin" for r in current.roles
            )
            if not is_admin_on_tenant:
                return jsonify({"error": "Insufficient permissions"}), 403

        existing = UserTenantRole.query.filter_by(
            user_id=user_id, tenant_id=tenant_id
        ).first()
        if existing:
            existing.role = role
        else:
            utr = UserTenantRole(
                user_id=user_id,
                tenant_id=tenant_id,
                role=role,
                granted_by=g.current_user.id,
            )
            db.session.add(utr)

    db.session.commit()
    return jsonify(user.to_dict(include_roles=True))


@users_bp.route("/<user_id>", methods=["DELETE"])
@require_role("admin")
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.is_active = False
    db.session.commit()
    return jsonify({"ok": True, "message": "User deactivated"})


@users_bp.route("/<user_id>/password", methods=["PUT"])
@require_role("viewer")
def change_password(user_id):
    current_user = g.current_user
    is_self = current_user.id == user_id
    is_admin = current_user.is_super_admin or any(
        r.role == "admin" for r in current_user.roles
    )

    if not is_self and not is_admin:
        return jsonify({"error": "Insufficient permissions"}), 403

    data = request.get_json(silent=True)
    if not data or not data.get("new_password"):
        return jsonify({"error": "new_password required"}), 400

    if len(data["new_password"]) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if is_self and not is_admin:
        if not data.get("current_password"):
            return jsonify({"error": "current_password required"}), 400
        user = db.session.get(User, user_id)
        if not user or not verify_password(data["current_password"], user.password_hash):
            return jsonify({"error": "Current password is incorrect"}), 401
    else:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

    user.password_hash = hash_password(data["new_password"])
    db.session.commit()
    return jsonify({"ok": True, "message": "Password updated"})


@users_bp.route("/<user_id>/roles/<tenant_id>", methods=["DELETE"])
@require_role("admin")
def remove_user_role(user_id, tenant_id):
    current = g.current_user
    if not current.is_super_admin:
        is_admin_on_tenant = any(
            r.tenant_id == tenant_id and r.role == "admin" for r in current.roles
        )
        if not is_admin_on_tenant:
            return jsonify({"error": "Insufficient permissions"}), 403

    role = UserTenantRole.query.filter_by(user_id=user_id, tenant_id=tenant_id).first()
    if not role:
        return jsonify({"error": "Role not found"}), 404

    db.session.delete(role)
    db.session.commit()
    return jsonify({"ok": True, "message": "Role removed"})

import time
from functools import wraps

import bcrypt
import jwt
from flask import current_app, g, jsonify, request

from .models import Tenant, User, db


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user):
    roles = {}
    for r in user.roles:
        if r.tenant:
            roles[r.tenant.slug] = r.role

    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.display_name,
        "is_super_admin": user.is_super_admin,
        "roles": roles,
        "exp": int(time.time()) + current_app.config["JWT_ACCESS_EXPIRY"],
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def create_refresh_token(user):
    payload = {
        "sub": user.id,
        "type": "refresh",
        "exp": int(time.time()) + current_app.config["JWT_REFRESH_EXPIRY"],
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header[7:]
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        if payload.get("type") == "refresh":
            return jsonify({"error": "Cannot use refresh token for API access"}), 401

        user = db.session.get(User, payload["sub"])
        if not user or not user.is_active:
            return jsonify({"error": "User not found or inactive"}), 401

        g.current_user = user
        g.token_payload = payload
        return f(*args, **kwargs)

    return decorated


def resolve_tenant():
    """Get tenant_id from X-Namespace header. Validate user access."""
    slug = request.headers.get("X-Namespace", "").strip().lower()
    if not slug:
        roles = g.token_payload.get("roles", {})
        slug = next(iter(roles), None)
    if not slug:
        return None
    tenant = Tenant.query.filter_by(slug=slug, is_active=True).first()
    if not tenant:
        return None
    user = g.current_user
    if not user.is_super_admin:
        roles = g.token_payload.get("roles", {})
        if slug not in roles:
            return None
    return tenant.id


def require_role(role):
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            user = g.current_user
            if user.is_super_admin:
                return f(*args, **kwargs)

            user_roles = {r.tenant.slug: r.role for r in user.roles if r.tenant}
            role_hierarchy = {"admin": 3, "editor": 2, "viewer": 1}
            required_level = role_hierarchy.get(role, 0)

            has_access = any(
                role_hierarchy.get(r, 0) >= required_level for r in user_roles.values()
            )
            if not has_access:
                return jsonify({"error": "Insufficient permissions"}), 403

            return f(*args, **kwargs)

        return decorated

    return decorator

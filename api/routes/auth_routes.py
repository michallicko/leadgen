from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from ..auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    require_auth,
    verify_password,
)
from ..models import User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(password, user.password_hash):
        return jsonify({"error": "Invalid email or password"}), 401

    if not user.is_active:
        return jsonify({"error": "Account is disabled"}), 401

    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify(
        {
            "access_token": create_access_token(user),
            "refresh_token": create_refresh_token(user),
            "user": user.to_dict(include_roles=True),
        }
    )


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    data = request.get_json(silent=True)
    if not data or not data.get("refresh_token"):
        return jsonify({"error": "refresh_token required"}), 400

    try:
        payload = decode_token(data["refresh_token"])
    except Exception:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    if payload.get("type") != "refresh":
        return jsonify({"error": "Not a refresh token"}), 401

    user = db.session.get(User, payload["sub"])
    if not user or not user.is_active:
        return jsonify({"error": "User not found or inactive"}), 401

    return jsonify(
        {
            "access_token": create_access_token(user),
        }
    )


@auth_bp.route("/me")
@require_auth
def me():
    user = g.current_user
    return jsonify(user.to_dict(include_roles=True))

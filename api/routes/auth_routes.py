import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from flask import Blueprint, current_app, g, jsonify, redirect, request

from ..auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    require_auth,
    verify_password,
)
from ..models import User, db
from ..services.iam_sync import find_or_create_local_user, sync_iam_roles

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login endpoint — proxies to IAM, falls back to local auth during migration.

    Flow:
    1. Try IAM proxy login (POST to IAM /api/auth/login)
    2. On success: find/create local user, sync roles, return IAM tokens
    3. On IAM failure: fall back to local email/password auth
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    # Try IAM proxy login first
    iam_base = current_app.config.get("IAM_BASE_URL")
    if iam_base:
        try:
            iam_resp = requests.post(
                f"{iam_base}/api/auth/login",
                json={"email": email, "password": password, "app": "leadgen"},
                timeout=10,
            )
            if iam_resp.status_code == 200:
                iam_data = iam_resp.json()
                iam_user = iam_data.get("user", {})
                iam_permissions = iam_user.get("permissions", [])

                # Find or create local user
                local_user = find_or_create_local_user(
                    {
                        "id": iam_user.get("id"),
                        "email": iam_user.get("email", email),
                        "name": iam_user.get("name", ""),
                    }
                )

                # Sync roles from IAM permissions
                sync_iam_roles(local_user, iam_permissions)

                # Update last login
                local_user.last_login_at = datetime.now(timezone.utc)
                db.session.commit()

                # Pass through IAM tokens
                return jsonify(
                    {
                        "access_token": iam_data.get("access_token"),
                        "refresh_token": iam_data.get("refresh_token"),
                        "user": local_user.to_dict(include_roles=True),
                    }
                )

            # IAM returned an error — check if it's a credentials error
            if iam_resp.status_code == 401:
                # Try local fallback (user might not be in IAM yet)
                logger.debug("IAM login returned 401 for %s, trying local auth", email)
            else:
                logger.warning(
                    "IAM login returned %s for %s",
                    iam_resp.status_code,
                    email,
                )
        except requests.RequestException as e:
            # IAM is unreachable — fall back to local auth
            logger.warning("IAM unreachable during login for %s: %s", email, e)

    # Fallback: local email/password auth (migration period)
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


@auth_bp.route("/iam/callback", methods=["GET"])
def iam_callback():
    """
    IAM OAuth callback — exchanges auth code for tokens, syncs user, redirects to frontend.

    IAM redirects here with ?code=AUTH_CODE after successful OAuth (Google/GitHub).
    We exchange the code server-side, find/create the local user, sync roles,
    and redirect to the frontend callback page with tokens in the URL hash.
    """
    code = request.args.get("code")
    error = request.args.get("error")
    login_required = request.args.get("login_required")

    # Handle error from IAM
    if error:
        logger.warning("IAM OAuth callback received error: %s", error)
        return redirect(f"/?error={error}")

    # Handle login_required redirect (IAM session expired or not authenticated)
    if login_required:
        return redirect("/?login_required=true")

    if not code:
        return redirect("/?error=missing_code")

    # Exchange auth code for tokens via IAM
    iam_base = current_app.config.get("IAM_BASE_URL")
    if not iam_base:
        logger.error("IAM_BASE_URL not configured, cannot exchange OAuth code")
        return redirect("/?error=iam_not_configured")

    try:
        exchange_resp = requests.post(
            f"{iam_base}/token/exchange",
            json={"code": code},
            timeout=10,
        )
        if exchange_resp.status_code != 200:
            logger.warning(
                "IAM token exchange failed with status %s: %s",
                exchange_resp.status_code,
                exchange_resp.text[:200],
            )
            return redirect("/?error=token_exchange_failed")

        token_data = exchange_resp.json()
        access_token = token_data.get("accessToken")
        refresh_token = token_data.get("refreshToken")

        if not access_token:
            logger.error("IAM token exchange returned no accessToken")
            return redirect("/?error=no_access_token")

    except requests.RequestException as e:
        logger.error("IAM token exchange request failed: %s", e)
        return redirect("/?error=iam_unreachable")

    # Decode the access token to get user info (without full verification —
    # we trust IAM since we just received this token from a server-side exchange)
    try:
        import jwt

        # Decode without verification — we trust this token from IAM server-side exchange
        payload = jwt.decode(access_token, options={"verify_signature": False})
        iam_user_id = payload.get("sub")
        email = payload.get("email", "")
        name = payload.get("name", "")
        permissions = payload.get("permissions", [])
    except Exception as e:
        logger.error("Failed to decode IAM access token: %s", e)
        return redirect("/?error=invalid_token")

    # Find or create local user and sync roles
    try:
        local_user = find_or_create_local_user(
            {
                "id": iam_user_id,
                "email": email,
                "name": name,
            }
        )
        sync_iam_roles(local_user, permissions)

        local_user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as e:
        logger.error("Failed to sync IAM user locally: %s", e)
        return redirect("/?error=user_sync_failed")

    # Serialize user data for frontend
    user_data = local_user.to_dict(include_roles=True)

    # Redirect to frontend callback page with tokens in URL hash (not query params,
    # so they don't appear in server logs or browser history)
    fragment = urlencode(
        {
            "access_token": access_token,
            "refresh_token": refresh_token or "",
            "user": json.dumps(user_data),
        }
    )
    return redirect(f"/auth/callback#{fragment}")


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """
    Refresh token endpoint — proxies to IAM if token looks like IAM token,
    falls back to local refresh for legacy tokens.
    """
    data = request.get_json(silent=True)
    if not data or not data.get("refresh_token"):
        return jsonify({"error": "refresh_token required"}), 400

    refresh_token = data["refresh_token"]

    # Try IAM refresh first
    iam_base = current_app.config.get("IAM_BASE_URL")
    if iam_base:
        try:
            iam_resp = requests.post(
                f"{iam_base}/api/auth/refresh",
                json={"refresh_token": refresh_token},
                timeout=10,
            )
            if iam_resp.status_code == 200:
                iam_data = iam_resp.json()
                return jsonify(
                    {
                        "access_token": iam_data.get("access_token"),
                    }
                )
        except requests.RequestException as e:
            logger.warning("IAM unreachable during refresh: %s", e)

    # Fallback: local HS256 refresh (migration period)
    try:
        payload = decode_token(refresh_token)
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


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    Logout endpoint — revokes refresh token at IAM (fire and forget).
    """
    data = request.get_json(silent=True)
    refresh_token = data.get("refresh_token") if data else None

    # Try to revoke at IAM
    iam_base = current_app.config.get("IAM_BASE_URL")
    if iam_base and refresh_token:
        try:
            requests.post(
                f"{iam_base}/api/auth/revoke",
                json={"refresh_token": refresh_token},
                timeout=5,
            )
        except requests.RequestException:
            pass  # Best effort — IAM may be unreachable

    return jsonify({"status": "ok"})


@auth_bp.route("/me")
@require_auth
def me():
    user = g.current_user
    return jsonify(user.to_dict(include_roles=True))

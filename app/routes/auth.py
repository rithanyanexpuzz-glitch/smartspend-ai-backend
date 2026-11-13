"""Authentication routes - register, login, profile, password reset."""

import secrets
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from app.extensions import db
from app.models.user import User
from app.utils.validators import validate_email, validate_password, sanitize_string

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    """Register a new user."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    try:
        email = validate_email(data.get("email"))
        password = validate_password(data.get("password"))
        full_name = sanitize_string(data.get("full_name", ""), 120)
        if not full_name:
            raise ValueError("Full name is required.")
    except ValueError as e:
        return jsonify(error=str(e)), 400

    if User.query.filter_by(email=email).first():
        return jsonify(error="An account with this email already exists."), 409

    user = User(email=email, full_name=full_name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify(
        message="Registration successful.",
        user=user.to_dict(),
        access_token=access_token,
        refresh_token=refresh_token,
    ), 201


@auth_bp.post("/demo-login")
def demo_login():
    """Instant one-click demo login without credentials."""
    demo_email = "demo@smartspend.ai"
    user = User.query.filter_by(email=demo_email).first()
    if not user:
        # Fallback to test user or first user
        user = User.query.first()

    if not user:
        return jsonify(error="Demo account not ready."), 404

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify(
        message="Demo login successful.",
        user=user.to_dict(),
        access_token=access_token,
        refresh_token=refresh_token,
    ), 200


@auth_bp.post("/login")
def login():
    """Authenticate user and return JWT tokens."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify(error="Email and password are required."), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify(error="Invalid email or password."), 401

    if not user.is_active:
        return jsonify(error="This account has been deactivated."), 403

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify(
        message="Login successful.",
        user=user.to_dict(),
        access_token=access_token,
        refresh_token=refresh_token,
    ), 200


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    """Refresh access token."""
    user_id = get_jwt_identity()
    access_token = create_access_token(identity=str(user_id))
    return jsonify(access_token=access_token), 200


@auth_bp.get("/profile")
@jwt_required()
def get_profile():
    """Get current user profile."""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify(error="User not found."), 404
    return jsonify(user=user.to_dict()), 200


@auth_bp.put("/profile")
@jwt_required()
def update_profile():
    """Update current user profile."""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify(error="User not found."), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    if "full_name" in data:
        full_name = sanitize_string(data["full_name"], 120)
        if not full_name:
            return jsonify(error="Full name is required."), 400
        user.full_name = full_name

    if "currency" in data:
        user.currency = str(data["currency"])[:10]

    # ── Notification preferences ───────────────────────────────
    if "phone" in data:
        phone = str(data["phone"]).strip()[:20] if data["phone"] else None
        user.phone = phone

    if "notify_email" in data:
        user.notify_email = bool(data["notify_email"])

    if "notify_whatsapp" in data:
        user.notify_whatsapp = bool(data["notify_whatsapp"])

    if "whatsapp_number" in data:
        wa = str(data["whatsapp_number"]).strip()[:20] if data["whatsapp_number"] else None
        user.whatsapp_number = wa

    db.session.commit()
    return jsonify(user=user.to_dict()), 200


@auth_bp.post("/change-password")
@jwt_required()
def change_password():
    """Change password for authenticated user."""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify(error="User not found."), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    current_password = str(data.get("current_password", ""))
    new_password = str(data.get("new_password", ""))

    if not user.check_password(current_password):
        return jsonify(error="Current password is incorrect."), 400

    try:
        new_password = validate_password(new_password)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    user.set_password(new_password)
    db.session.commit()
    return jsonify(message="Password changed successfully."), 200


@auth_bp.post("/forgot-password")
def forgot_password():
    """Request password reset token."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    email = str(data.get("email", "")).strip().lower()
    if not email:
        return jsonify(error="Email is required."), 400

    user = User.query.filter_by(email=email).first()
    if user:
        token = secrets.token_urlsafe(48)
        user.reset_token = token
        user.reset_token_exp = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()
        # In production, send email with the token.
        # For now we return it in the response for testing.

    # Always return success to prevent email enumeration
    return jsonify(
        message="If an account with that email exists, a reset link has been sent."
    ), 200


@auth_bp.post("/reset-password")
def reset_password():
    """Reset password using token."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    token = str(data.get("token", ""))
    new_password = str(data.get("new_password", ""))

    if not token:
        return jsonify(error="Reset token is required."), 400

    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_exp or user.reset_token_exp < datetime.utcnow():
        return jsonify(error="Invalid or expired reset token."), 400

    try:
        new_password = validate_password(new_password)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    user.set_password(new_password)
    user.reset_token = None
    user.reset_token_exp = None
    db.session.commit()

    return jsonify(message="Password reset successful. Please login with your new password."), 200

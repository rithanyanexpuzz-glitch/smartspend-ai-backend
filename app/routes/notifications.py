"""Notification management routes."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.notification import Notification

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.get("/")
@jwt_required()
def list_notifications():
    """List notifications for the current user (newest first)."""
    user_id = int(get_jwt_identity())
    limit = request.args.get("limit", 50, type=int)

    items = (
        Notification.query
        .filter_by(user_id=user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )
    unread = Notification.query.filter_by(user_id=user_id, is_read=False).count()

    return jsonify(
        notifications=[n.to_dict() for n in items],
        unread_count=unread,
    ), 200


@notifications_bp.put("/<int:notif_id>/read")
@jwt_required()
def mark_read(notif_id):
    """Mark a single notification as read."""
    user_id = int(get_jwt_identity())
    notif = Notification.query.filter_by(id=notif_id, user_id=user_id).first()
    if not notif:
        return jsonify(error="Notification not found."), 404

    notif.is_read = True
    db.session.commit()
    return jsonify(notification=notif.to_dict()), 200


@notifications_bp.put("/read-all")
@jwt_required()
def mark_all_read():
    """Mark all notifications as read."""
    user_id = int(get_jwt_identity())
    Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify(message="All notifications marked as read."), 200


@notifications_bp.delete("/<int:notif_id>")
@jwt_required()
def delete_notification(notif_id):
    """Delete a single notification."""
    user_id = int(get_jwt_identity())
    notif = Notification.query.filter_by(id=notif_id, user_id=user_id).first()
    if not notif:
        return jsonify(error="Notification not found."), 404

    db.session.delete(notif)
    db.session.commit()
    return jsonify(deleted=True, id=notif_id), 200


@notifications_bp.delete("/")
@jwt_required()
def clear_all():
    """Delete all notifications for the current user."""
    user_id = int(get_jwt_identity())
    count = Notification.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify(deleted=True, count=count), 200

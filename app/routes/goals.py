"""Savings Goals management routes."""
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.savings_goal import SavingsGoal
from app.utils.validators import validate_amount

goals_bp = Blueprint("goals", __name__)


@goals_bp.get("/")
@jwt_required()
def list_goals():
    """List all savings goals for the user."""
    user_id = int(get_jwt_identity())
    goals = SavingsGoal.query.filter_by(user_id=user_id).order_by(SavingsGoal.created_at.desc()).all()
    return jsonify(goals=[g.to_dict() for g in goals]), 200


@goals_bp.post("/")
@jwt_required()
def create_goal():
    """Create a new savings goal."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify(error="Title is required."), 400

    try:
        target_amount = validate_amount(data.get("target_amount"))
        saved_amount = float(data.get("saved_amount", 0.0) or 0.0)
        if saved_amount < 0:
            saved_amount = 0.0
    except ValueError as e:
        return jsonify(error=str(e)), 400

    target_date = None
    if data.get("target_date"):
        try:
            target_date = datetime.strptime(data["target_date"], "%Y-%m-%d").date()
        except ValueError:
            pass

    goal = SavingsGoal(
        user_id=user_id,
        title=title,
        target_amount=target_amount,
        saved_amount=saved_amount,
        target_date=target_date,
        category=str(data.get("category", "General")),
        color=str(data.get("color", "#10b981")),
    )
    db.session.add(goal)
    db.session.commit()
    return jsonify(goal=goal.to_dict()), 201


@goals_bp.put("/<int:goal_id>")
@jwt_required()
def update_goal(goal_id):
    """Update goal details or add savings to it."""
    user_id = int(get_jwt_identity())
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=user_id).first()
    if not goal:
        return jsonify(error="Goal not found."), 404

    data = request.get_json(silent=True) or {}

    if "title" in data and str(data["title"]).strip():
        goal.title = str(data["title"]).strip()

    if "target_amount" in data:
        try:
            goal.target_amount = validate_amount(data["target_amount"])
        except ValueError as e:
            return jsonify(error=str(e)), 400

    if "saved_amount" in data:
        try:
            goal.saved_amount = max(0.0, float(data["saved_amount"]))
        except (ValueError, TypeError):
            pass

    # Quick Add Savings (e.g. user adds ₹500 today)
    if "add_amount" in data:
        try:
            add_val = float(data["add_amount"])
            goal.saved_amount = max(0.0, float(goal.saved_amount) + add_val)
        except (ValueError, TypeError):
            pass

    if "category" in data:
        goal.category = str(data["category"])
    if "color" in data:
        goal.color = str(data["color"])

    if float(goal.saved_amount) >= float(goal.target_amount):
        goal.is_completed = True

    db.session.commit()
    return jsonify(goal=goal.to_dict()), 200


@goals_bp.delete("/<int:goal_id>")
@jwt_required()
def delete_goal(goal_id):
    """Delete a goal."""
    user_id = int(get_jwt_identity())
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=user_id).first()
    if not goal:
        return jsonify(error="Goal not found."), 404

    db.session.delete(goal)
    db.session.commit()
    return jsonify(deleted=True, id=goal_id), 200

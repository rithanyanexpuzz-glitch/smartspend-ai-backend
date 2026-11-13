"""Budget management routes."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.budget import Budget
from app.services.budget_service import get_budget_status
from app.utils.validators import validate_amount, validate_month

budgets_bp = Blueprint("budgets", __name__)


@budgets_bp.get("/")
@jwt_required()
def list_budgets():
    """List all budgets with status for a given month."""
    user_id = int(get_jwt_identity())
    try:
        month = validate_month(request.args.get("month"))
    except ValueError as e:
        return jsonify(error=str(e)), 400

    statuses = get_budget_status(user_id, month)
    return jsonify(budgets=statuses, month=month), 200


@budgets_bp.post("/")
@jwt_required()
def create_or_update_budget():
    """Create or update a budget for a category."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    category_name = str(data.get("category_name") or data.get("category", "")).strip()
    if not category_name:
        return jsonify(error="Category name is required."), 400

    try:
        monthly_limit = validate_amount(data.get("monthly_limit"), "Monthly limit")
    except ValueError as e:
        return jsonify(error=str(e)), 400

    weekly_limit = data.get("weekly_limit")
    if weekly_limit:
        try:
            weekly_limit = validate_amount(weekly_limit, "Weekly limit")
        except ValueError:
            weekly_limit = None

    budget = Budget.query.filter_by(user_id=user_id, category_name=category_name).first()
    if budget:
        budget.monthly_limit = monthly_limit
        if weekly_limit:
            budget.weekly_limit = weekly_limit
        budget.alert_50 = data.get("alert_50", budget.alert_50)
        budget.alert_80 = data.get("alert_80", budget.alert_80)
        budget.alert_100 = data.get("alert_100", budget.alert_100)
        budget.is_active = data.get("is_active", budget.is_active)
    else:
        budget = Budget(
            user_id=user_id,
            category_name=category_name,
            monthly_limit=monthly_limit,
            weekly_limit=weekly_limit,
            alert_50=data.get("alert_50", True),
            alert_80=data.get("alert_80", True),
            alert_100=data.get("alert_100", True),
        )
        db.session.add(budget)

    db.session.commit()
    return jsonify(budget=budget.to_dict()), 201


@budgets_bp.delete("/<int:budget_id>")
@jwt_required()
def delete_budget(budget_id):
    """Delete a budget."""
    user_id = int(get_jwt_identity())
    budget = Budget.query.filter_by(id=budget_id, user_id=user_id).first()
    if not budget:
        return jsonify(error="Budget not found."), 404

    db.session.delete(budget)
    db.session.commit()
    return jsonify(deleted=True, id=budget_id), 200

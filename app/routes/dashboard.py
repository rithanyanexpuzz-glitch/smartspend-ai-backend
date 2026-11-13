"""Dashboard data routes."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.insights_service import (
    get_financial_summary,
    get_category_breakdown,
    get_monthly_trends,
    get_recent_transactions,
)
from app.services.budget_service import get_budget_status
from app.utils.validators import validate_month

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
@jwt_required()
def get_dashboard():
    """Get complete dashboard data for the current user."""
    user_id = int(get_jwt_identity())

    try:
        month = validate_month(request.args.get("month"))
    except ValueError as e:
        return jsonify(error=str(e)), 400

    summary = get_financial_summary(user_id, month)
    categories = get_category_breakdown(user_id, month)
    trends = get_monthly_trends(user_id, 6)
    budgets = get_budget_status(user_id, month)
    recent = get_recent_transactions(user_id, 10)

    # Find highest spending category
    highest_category = categories[0] if categories else None

    return jsonify(
        month=month,
        summary=summary,
        category_breakdown=categories,
        monthly_trends=trends,
        budgets=budgets,
        recent_transactions=recent,
        highest_category=highest_category,
    ), 200


@dashboard_bp.get("/summary")
@jwt_required()
def get_summary():
    """Get financial summary for a month."""
    user_id = int(get_jwt_identity())
    try:
        month = validate_month(request.args.get("month"))
    except ValueError as e:
        return jsonify(error=str(e)), 400

    summary = get_financial_summary(user_id, month)
    return jsonify(summary=summary, month=month), 200

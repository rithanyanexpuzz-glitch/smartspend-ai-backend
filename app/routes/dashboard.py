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

    # Calculate Financial Health Score (0 - 100)
    # Factors:
    # 1. Savings rate (max 50 pts)
    # 2. Budget adherence (max 30 pts)
    # 3. Expense to Income ratio (max 20 pts)
    income_val = summary.get("total_income", 0.0)
    expense_val = summary.get("total_expense", 0.0)
    savings_rate = summary.get("savings_rate", 0.0)

    score = 50  # base
    if income_val > 0:
        savings_pts = min(40, max(0, int(savings_rate * 0.8)))
        ratio_pts = 20 if expense_val <= (income_val * 0.7) else (10 if expense_val <= income_val else 0)
        over_budget_count = sum(1 for b in budgets if b.get("alert") == "over budget")
        budget_pts = max(0, 30 - (over_budget_count * 15))
        score = min(100, max(15, savings_pts + ratio_pts + budget_pts + 10))

    health_status = "Excellent" if score >= 80 else ("Good" if score >= 65 else ("Fair" if score >= 45 else "Needs Attention"))

    return jsonify(
        month=month,
        summary=summary,
        category_breakdown=categories,
        monthly_trends=trends,
        budgets=budgets,
        recent_transactions=recent,
        highest_category=highest_category,
        health_score={
            "score": score,
            "status": health_status,
            "savings_rate": savings_rate,
        },
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

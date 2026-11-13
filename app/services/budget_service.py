"""Budget calculation service."""

from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import func, extract

from app.extensions import db
from app.models.expense import Expense
from app.models.budget import Budget
from app.models.notification import Notification
from app.models.user import User


def get_budget_status(user_id, month=None):
    """
    Calculate budget status for all active budgets of a user.
    Preserves original 80% and 100% alert logic, adds 50% threshold.
    """
    if month:
        year, mon = map(int, month.split("-"))
    else:
        today = date.today()
        year, mon = today.year, today.month

    budgets = Budget.query.filter_by(user_id=user_id, is_active=True).all()
    if not budgets:
        return []

    statuses = []
    for budget in budgets:
        spent_row = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(
            Expense.user_id == user_id,
            Expense.category_name == budget.category_name,
            extract("year", Expense.expense_date) == year,
            extract("month", Expense.expense_date) == mon,
        ).scalar()

        spent = float(spent_row)
        limit_val = float(budget.monthly_limit)
        percentage = (spent / limit_val * 100) if limit_val > 0 else 0
        remaining = max(limit_val - spent, 0)

        if spent > limit_val:
            alert = "over budget"
        elif percentage >= 80:
            alert = "near limit"
        elif percentage >= 50:
            alert = "halfway"
        else:
            alert = ""

        statuses.append({
            "id": budget.id,
            "category_name": budget.category_name,
            "spent": spent,
            "limit": limit_val,
            "remaining": remaining,
            "percentage": round(percentage, 1),
            "alert": alert,
            "weekly_limit": float(budget.weekly_limit) if budget.weekly_limit else None,
        })

    return statuses


def check_and_notify_budget(user_id, category_name, month=None):
    """Check budget after expense is added and create notifications + send external alerts."""
    if month:
        year, mon = map(int, month.split("-"))
    else:
        today = date.today()
        year, mon = today.year, today.month

    budget = Budget.query.filter_by(
        user_id=user_id, category_name=category_name, is_active=True
    ).first()

    if not budget:
        return None

    spent_row = db.session.query(
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(
        Expense.user_id == user_id,
        Expense.category_name == category_name,
        extract("year", Expense.expense_date) == year,
        extract("month", Expense.expense_date) == mon,
    ).scalar()

    spent = float(spent_row)
    limit_val = float(budget.monthly_limit)
    percentage = (spent / limit_val * 100) if limit_val > 0 else 0

    alert_type = None

    if spent > limit_val and budget.alert_100:
        Notification.create_notification(
            user_id=user_id,
            title=f"Over budget: {category_name}",
            message=f"You've spent ₹{spent:,.2f} which exceeds your ₹{limit_val:,.2f} monthly limit for {category_name}.",
            notif_type="alert",
            category=category_name,
        )
        alert_type = "over budget"

    elif percentage >= 80 and budget.alert_80:
        Notification.create_notification(
            user_id=user_id,
            title=f"Budget warning: {category_name}",
            message=f"You've used {percentage:.0f}% of your {category_name} budget (₹{spent:,.2f} of ₹{limit_val:,.2f}).",
            notif_type="warning",
            category=category_name,
        )
        alert_type = "near limit"

    elif percentage >= 50 and budget.alert_50:
        Notification.create_notification(
            user_id=user_id,
            title=f"Budget update: {category_name}",
            message=f"You've used {percentage:.0f}% of your {category_name} budget.",
            notif_type="info",
            category=category_name,
        )
        alert_type = "halfway"

    # ── Fire external notifications (email + WhatsApp) ────────
    if alert_type:
        try:
            from app.services.notification_service import dispatch_budget_alert
            user = User.query.get(user_id)
            if user:
                dispatch_budget_alert(
                    user=user,
                    alert_type=alert_type,
                    category=category_name,
                    spent=spent,
                    limit=limit_val,
                    percentage=percentage,
                )
        except Exception as e:
            # Never block the main flow if notifications fail
            import logging
            logging.getLogger(__name__).error(f"External notification dispatch failed: {e}")

    return alert_type or ""


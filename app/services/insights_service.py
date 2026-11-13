"""AI Financial Insights Service."""

from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict
from sqlalchemy import func, extract

from app.extensions import db
from app.models.expense import Expense
from app.models.income import Income


def get_financial_summary(user_id, month=None):
    """Get total income, expenses, balance, savings for a month."""
    if month:
        year, mon = map(int, month.split("-"))
    else:
        today = date.today()
        year, mon = today.year, today.month

    total_income = db.session.query(
        func.coalesce(func.sum(Income.amount), 0)
    ).filter(
        Income.user_id == user_id,
        extract("year", Income.income_date) == year,
        extract("month", Income.income_date) == mon,
    ).scalar()

    total_expenses = db.session.query(
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(
        Expense.user_id == user_id,
        extract("year", Expense.expense_date) == year,
        extract("month", Expense.expense_date) == mon,
    ).scalar()

    total_income = float(total_income)
    total_expenses = float(total_expenses)

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": total_income - total_expenses,
        "savings": max(total_income - total_expenses, 0),
        "savings_rate": round(
            ((total_income - total_expenses) / total_income * 100)
            if total_income > 0 else 0, 1
        ),
    }


def get_category_breakdown(user_id, month=None):
    """Get expense totals grouped by category."""
    if month:
        year, mon = map(int, month.split("-"))
    else:
        today = date.today()
        year, mon = today.year, today.month

    rows = db.session.query(
        Expense.category_name, func.sum(Expense.amount).label("total")
    ).filter(
        Expense.user_id == user_id,
        extract("year", Expense.expense_date) == year,
        extract("month", Expense.expense_date) == mon,
    ).group_by(Expense.category_name).order_by(func.sum(Expense.amount).desc()).all()

    return [{"category": r.category_name, "total": float(r.total)} for r in rows]


def get_monthly_trends(user_id, months=6):
    """Get expense totals for the last N months."""
    today = date.today()
    trends = []
    for i in range(months - 1, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1

        total = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(
            Expense.user_id == user_id,
            extract("year", Expense.expense_date) == y,
            extract("month", Expense.expense_date) == m,
        ).scalar()

        income = db.session.query(
            func.coalesce(func.sum(Income.amount), 0)
        ).filter(
            Income.user_id == user_id,
            extract("year", Income.income_date) == y,
            extract("month", Income.income_date) == m,
        ).scalar()

        trends.append({
            "month": f"{y}-{m:02d}",
            "expenses": float(total),
            "income": float(income),
        })

    return trends


def get_ai_insights(user_id):
    """Generate AI-driven financial insights based on user data."""
    today = date.today()
    current_month = f"{today.year}-{today.month:02d}"

    prev_month_num = today.month - 1 if today.month > 1 else 12
    prev_year = today.year if today.month > 1 else today.year - 1
    prev_month = f"{prev_year}-{prev_month_num:02d}"

    insights = []

    # Current vs previous month comparison
    current_summary = get_financial_summary(user_id, current_month)
    prev_summary = get_financial_summary(user_id, prev_month)

    if prev_summary["total_expenses"] > 0:
        change = current_summary["total_expenses"] - prev_summary["total_expenses"]
        pct = (change / prev_summary["total_expenses"]) * 100
        if change > 0:
            insights.append({
                "type": "warning",
                "title": "Spending increased",
                "message": f"Your expenses are up by ₹{change:,.2f} ({pct:+.1f}%) compared to last month.",
                "icon": "📈",
            })
        elif change < 0:
            insights.append({
                "type": "success",
                "title": "Spending decreased",
                "message": f"Great job! Your expenses are down by ₹{abs(change):,.2f} ({pct:.1f}%) compared to last month.",
                "icon": "📉",
            })

    # Highest spending category
    categories = get_category_breakdown(user_id, current_month)
    if categories:
        top = categories[0]
        insights.append({
            "type": "info",
            "title": f"Top spending: {top['category']}",
            "message": f"Your highest expense category this month is {top['category']} at ₹{top['total']:,.2f}.",
            "icon": "🏷️",
        })

    # Savings rate
    if current_summary["total_income"] > 0:
        rate = current_summary["savings_rate"]
        if rate >= 30:
            insights.append({
                "type": "success",
                "title": "Excellent savings rate",
                "message": f"You're saving {rate:.1f}% of your income this month. Keep it up!",
                "icon": "💰",
            })
        elif rate >= 10:
            insights.append({
                "type": "info",
                "title": "Moderate savings",
                "message": f"You're saving {rate:.1f}% of your income. Try to increase it to 20-30%.",
                "icon": "💡",
            })
        elif rate < 10:
            insights.append({
                "type": "warning",
                "title": "Low savings rate",
                "message": f"Your savings rate is only {rate:.1f}%. Consider reducing discretionary spending.",
                "icon": "⚠️",
            })

    # Unusual expenses (any single expense > 30% of total)
    if current_summary["total_expenses"] > 0:
        threshold = current_summary["total_expenses"] * 0.3
        large_expenses = Expense.query.filter(
            Expense.user_id == user_id,
            Expense.amount > threshold,
            extract("year", Expense.expense_date) == today.year,
            extract("month", Expense.expense_date) == today.month,
        ).order_by(Expense.amount.desc()).limit(3).all()

        for exp in large_expenses:
            insights.append({
                "type": "alert",
                "title": "Large expense detected",
                "message": f"₹{float(exp.amount):,.2f} for '{exp.description}' represents a significant portion of your monthly spending.",
                "icon": "🔍",
            })

    # Compare category spending with previous month
    prev_categories = {r["category"]: r["total"] for r in get_category_breakdown(user_id, prev_month)}
    for cat in categories[:3]:
        prev_total = prev_categories.get(cat["category"], 0)
        if prev_total > 0:
            cat_change = ((cat["total"] - prev_total) / prev_total) * 100
            if cat_change > 50:
                insights.append({
                    "type": "warning",
                    "title": f"{cat['category']} spending spike",
                    "message": f"Your {cat['category']} spending jumped {cat_change:.0f}% compared to last month.",
                    "icon": "⬆️",
                })

    if not insights:
        insights.append({
            "type": "info",
            "title": "Start tracking",
            "message": "Add your income and expenses to get personalized financial insights.",
            "icon": "📊",
        })

    return insights


def get_recent_transactions(user_id, limit=10):
    """Get most recent expenses and incomes combined."""
    expenses = Expense.query.filter_by(user_id=user_id).order_by(
        Expense.expense_date.desc(), Expense.created_at.desc()
    ).limit(limit).all()

    incomes = Income.query.filter_by(user_id=user_id).order_by(
        Income.income_date.desc(), Income.created_at.desc()
    ).limit(limit).all()

    transactions = []
    for e in expenses:
        transactions.append({
            "id": e.id,
            "type": "expense",
            "description": e.description,
            "amount": float(e.amount),
            "category": e.category_name,
            "date": e.expense_date.isoformat(),
            "created_at": e.created_at.isoformat(),
        })
    for i in incomes:
        transactions.append({
            "id": i.id,
            "type": "income",
            "description": i.description,
            "amount": float(i.amount),
            "category": i.category,
            "date": i.income_date.isoformat(),
            "created_at": i.created_at.isoformat(),
        })

    transactions.sort(key=lambda t: t["date"], reverse=True)
    return transactions[:limit]

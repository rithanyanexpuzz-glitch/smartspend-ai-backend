"""AI Financial Advisor and SMS / UPI Parser service & routes."""
import re
from datetime import datetime, date
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, extract

from app.extensions import db
from app.models.expense import Expense
from app.models.income import Income
from app.models.budget import Budget
from app.services.ml_categorizer import get_categorizer

advisor_bp = Blueprint("advisor", __name__)


# ─────────────────────────────────────────────────────────────
# 1. SMS / UPI PARSER LOGIC
# ─────────────────────────────────────────────────────────────

def parse_bank_sms(sms_text):
    """
    Parse Indian Bank / UPI transaction SMS into Expense metadata.
    Supported Banks: HDFC, SBI, ICICI, Axis, Kotak, PayTM, PhonePe, GPay, etc.
    """
    text = sms_text.strip()
    result = {
        "is_valid": False,
        "type": "debit",
        "amount": None,
        "merchant": "Unknown Merchant",
        "predicted_category": "Other",
        "date": date.today().isoformat(),
        "account": None,
    }

    # Detect Debit vs Credit
    if re.search(r"\b(debited|spent|paid|withdrawn|purchase|transferred to)\b", text, re.IGNORECASE):
        result["type"] = "debit"
    elif re.search(r"\b(credited|received|deposited|refund)\b", text, re.IGNORECASE):
        result["type"] = "credit"
    else:
        # Default assume debit if money mentioned
        result["type"] = "debit"

    # Match Amount: Rs. 500, Rs.500.00, INR 1,200.50, ₹450
    amt_match = re.search(
        r"(?:(?:Rs\.?|INR|₹)\s*|\bRs\b\s*)([0-9,]+(?:\.[0-9]{1,2})?)",
        text,
        re.IGNORECASE,
    )
    if amt_match:
        amt_str = amt_match.group(1).replace(",", "")
        try:
            result["amount"] = float(amt_str)
            result["is_valid"] = True
        except ValueError:
            pass

    # Match Merchant: "at SWIGGY", "to ZOMATO", "vpa xxx@upi", "info: UBER"
    merchant_match = re.search(
        r"(?:at|to|info[:\s]+|vpa\s+)([A-Za-z0-9\.\s\-_@]+?)(?:\s+(?:on|ref|upi|avl|bal|val|thru|using|ending)|\.|$)",
        text,
        re.IGNORECASE,
    )
    if merchant_match:
        m = merchant_match.group(1).strip()
        # Clean up words like 'your', 'account'
        m = re.sub(r"^(a/c|acct|account)\s*", "", m, flags=re.IGNORECASE)
        if len(m) > 1 and len(m) < 40:
            result["merchant"] = m.title()

    # If merchant found, predict category using ML categorizer
    desc = f"{result['merchant']} {text}"
    categorizer = get_categorizer()
    predicted_cat, conf = categorizer.predict(desc)
    result["predicted_category"] = predicted_cat
    result["confidence"] = round(conf, 2)

    return result


@advisor_bp.post("/parse-sms")
@jwt_required()
def parse_sms_endpoint():
    """Endpoint to parse raw SMS or UPI message into transaction fields."""
    data = request.get_json(silent=True) or {}
    text = str(data.get("sms_text", "")).strip()
    if not text:
        return jsonify(error="SMS text is required."), 400

    parsed = parse_bank_sms(text)
    return jsonify(parsed), 200


# ─────────────────────────────────────────────────────────────
# 2. AI FINANCIAL ADVISOR CHATBOT
# ─────────────────────────────────────────────────────────────

def get_financial_summary(user_id):
    """Fetch current month spending and income stats for user."""
    today = date.today()
    y, m = today.year, today.month

    total_expense = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.user_id == user_id,
        extract("year", Expense.expense_date) == y,
        extract("month", Expense.expense_date) == m,
    ).scalar()

    total_income = db.session.query(func.coalesce(func.sum(Income.amount), 0)).filter(
        Income.user_id == user_id,
        extract("year", Income.income_date) == y,
        extract("month", Income.income_date) == m,
    ).scalar()

    # Category breakdown
    cat_rows = db.session.query(
        Expense.category_name,
        func.sum(Expense.amount),
    ).filter(
        Expense.user_id == user_id,
        extract("year", Expense.expense_date) == y,
        extract("month", Expense.expense_date) == m,
    ).group_by(Expense.category_name).order_by(func.sum(Expense.amount).desc()).all()

    top_categories = [{"category": r[0], "amount": float(r[1])} for r in cat_rows[:3]]

    # Active budgets
    budgets = Budget.query.filter_by(user_id=user_id, is_active=True).all()
    budget_count = len(budgets)

    return {
        "income": float(total_income),
        "expense": float(total_expense),
        "savings": float(total_income - total_expense),
        "top_categories": top_categories,
        "budget_count": budget_count,
        "month_name": today.strftime("%B %Y"),
    }


def generate_advisor_response(user_query, stats):
    """Rule & Intelligence based financial advice generator tailored to Indian users."""
    q = user_query.lower()
    income = stats["income"]
    expense = stats["expense"]
    savings = stats["savings"]
    top_cats = stats["top_categories"]

    top_cat_str = ", ".join([f"{c['category']} (₹{c['amount']:,.0f})" for c in top_cats]) if top_cats else "None yet"

    if any(k in q for k in ["how much spent", "total spent", "expense", "செலவு"]):
        return (
            f"📊 **This Month's Spending ({stats['month_name']}):**\n\n"
            f"• **Total Spent:** ₹{expense:,.2f}\n"
            f"• **Top Spending Areas:** {top_cat_str}\n"
            f"• **Current Savings Balance:** ₹{savings:,.2f}\n\n"
            f"💡 *Tip:* Check your Budgets page to make sure you stay under your monthly limits!"
        )

    elif any(k in q for k in ["save", "saving", "சேமிக்க", "how to save", "tips"]):
        tips = [
            f"1. **Follow the 50/30/20 Rule:** Allocate 50% for Needs, 30% for Wants, and 20% directly into Savings/Investments.",
            f"2. **Cut Top Leaks:** Your highest spending is currently in **{top_cats[0]['category'] if top_cats else 'daily expenses'}**. Trimming 15% here could save you ₹{(top_cats[0]['amount'] * 0.15) if top_cats else 1000:,.0f} this month!",
            f"3. **Use Savings Goals:** Create a dedicated goal in the new **Savings Goals** tab to automatically lock away savings.",
        ]
        return "💰 **Here are actionable savings tips for you:**\n\n" + "\n\n".join(tips)

    elif any(k in q for k in ["salary", "income", "வருமானம்", "balance"]):
        return (
            f"💵 **Your Cash Flow Summary:**\n\n"
            f"• **Total Income:** ₹{income:,.2f}\n"
            f"• **Total Outflow:** ₹{expense:,.2f}\n"
            f"• **Net Savings:** ₹{savings:,.2f}\n"
            f"• **Savings Rate:** {round((savings/income*100), 1) if income > 0 else 0}%\n\n"
            f"{'🎉 Great job maintaining positive savings!' if savings > 0 else '⚠️ Your spending exceeds your income this month. Consider reviewing non-essential purchases.'}"
        )

    elif any(k in q for k in ["budget", "limit"]):
        return (
            f"🎯 You currently have **{stats['budget_count']} active budget(s)** set up.\n\n"
            f"Remember, SmartSpend AI automatically sends you **50%, 80% and 100% threshold alerts** to your Email and WhatsApp "
            f"so you never overspend without realizing!"
        )

    else:
        return (
            f"Hello! I am your **SmartSpend AI Financial Advisor** 🤖\n\n"
            f"Here is a quick snapshot of your finances for **{stats['month_name']}**:\n"
            f"• Income: ₹{income:,.0f} | Spent: ₹{expense:,.0f} | Saved: ₹{savings:,.0f}\n\n"
            f"You can ask me questions like:\n"
            f"👉 *'How much did I spend this month?'*\n"
            f"👉 *'How can I save more money?'*\n"
            f"👉 *'What is my savings rate?'*"
        )


@advisor_bp.post("/chat")
@jwt_required()
def advisor_chat():
    """Chat endpoint with AI Financial Advisor."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    stats = get_financial_summary(user_id)
    response_text = generate_advisor_response(message, stats)

    return jsonify({
        "reply": response_text,
        "stats": stats,
    }), 200

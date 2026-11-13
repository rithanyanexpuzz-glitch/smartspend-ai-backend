"""Report generation and download routes."""

import io
from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.report_service import (
    generate_csv_report,
    generate_excel_report,
    generate_pdf_report,
    generate_income_vs_expense_report,
)
from app.utils.validators import validate_month
from app.models.expense import Expense
from app.models.income import Income
from app.extensions import db
from sqlalchemy import extract, func
import datetime

reports_bp = Blueprint("reports", __name__)


@reports_bp.get("/summary")
@jwt_required()
def report_summary():
    """Get a financial summary for a given period."""
    user_id = int(get_jwt_identity())
    period = request.args.get("period", "month")
    now = datetime.date.today()

    if period == "month":
        month_str = f"{now.year}-{now.month:02d}"
    else:
        month_str = request.args.get("month", f"{now.year}-{now.month:02d}")

    try:
        year, month = map(int, month_str.split("-"))
    except (ValueError, AttributeError):
        year, month = now.year, now.month

    total_expense = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        extract("year", Expense.expense_date) == year,
        extract("month", Expense.expense_date) == month,
    ).scalar() or 0

    total_income = db.session.query(func.sum(Income.amount)).filter(
        Income.user_id == user_id,
        extract("year", Income.income_date) == year,
        extract("month", Income.income_date) == month,
    ).scalar() or 0

    return jsonify(
        period=month_str,
        total_income=float(total_income),
        total_expense=float(total_expense),
        net_savings=float(total_income - total_expense),
        savings_rate=round(float((total_income - total_expense) / total_income * 100), 1) if total_income else 0,
    ), 200



@reports_bp.get("/csv")
@jwt_required()
def download_csv():
    """Download monthly expense report as CSV."""
    user_id = int(get_jwt_identity())
    try:
        month = validate_month(request.args.get("month"))
    except ValueError as e:
        return jsonify(error=str(e)), 400

    category = request.args.get("category")
    csv_data, count = generate_csv_report(user_id, month, category)

    return send_file(
        io.BytesIO(csv_data.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"smartspend_expenses_{month}.csv",
    )


@reports_bp.get("/excel")
@jwt_required()
def download_excel():
    """Download monthly expense report as Excel."""
    user_id = int(get_jwt_identity())
    try:
        month = validate_month(request.args.get("month"))
    except ValueError as e:
        return jsonify(error=str(e)), 400

    category = request.args.get("category")

    try:
        excel_data, count = generate_excel_report(user_id, month, category)
    except ImportError as e:
        return jsonify(error=str(e)), 500

    return send_file(
        excel_data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"smartspend_expenses_{month}.xlsx",
    )


@reports_bp.get("/pdf")
@jwt_required()
def download_pdf():
    """Download monthly expense report as PDF."""
    user_id = int(get_jwt_identity())
    try:
        month = validate_month(request.args.get("month"))
    except ValueError as e:
        return jsonify(error=str(e)), 400

    category = request.args.get("category")

    try:
        pdf_data, count = generate_pdf_report(user_id, month, category)
    except ImportError as e:
        return jsonify(error=str(e)), 500

    return send_file(
        pdf_data,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"smartspend_expenses_{month}.pdf",
    )


@reports_bp.get("/income-vs-expense")
@jwt_required()
def income_vs_expense():
    """Get income vs expense comparison for last N months."""
    user_id = int(get_jwt_identity())
    months = min(int(request.args.get("months", 6)), 12)
    data = generate_income_vs_expense_report(user_id, months)
    return jsonify(data=data), 200

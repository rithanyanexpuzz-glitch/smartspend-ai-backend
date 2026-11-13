"""Income management routes."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import extract

from app.extensions import db
from app.models.income import Income
from app.utils.validators import (
    validate_amount, validate_description, validate_date,
    validate_month, sanitize_string,
)

income_bp = Blueprint("income", __name__)

INCOME_CATEGORIES = ("Salary", "Business", "Freelance", "Investment", "Rental", "Other")


@income_bp.get("/")
@jwt_required()
def list_income():
    """List income records with optional filters."""
    user_id = int(get_jwt_identity())
    month = request.args.get("month")
    category = request.args.get("category")
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 50)), 100)

    query = Income.query.filter_by(user_id=user_id)

    if month:
        try:
            month = validate_month(month)
            year, mon = map(int, month.split("-"))
            query = query.filter(
                extract("year", Income.income_date) == year,
                extract("month", Income.income_date) == mon,
            )
        except ValueError as e:
            return jsonify(error=str(e)), 400

    if category:
        if category not in INCOME_CATEGORIES:
            return jsonify(error=f"Category must be one of: {', '.join(INCOME_CATEGORIES)}"), 400
        query = query.filter(Income.category == category)

    paginated = query.order_by(Income.income_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify(
        incomes=[i.to_dict() for i in paginated.items],
        total=paginated.total,
        page=paginated.page,
        pages=paginated.pages,
        has_next=paginated.has_next,
    ), 200


@income_bp.post("/")
@jwt_required()
def create_income():
    """Add a new income record."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    try:
        amount = validate_amount(data.get("amount"))
        description = validate_description(data.get("description"))
        income_date = validate_date(data.get("income_date") or data.get("date"))
    except ValueError as e:
        return jsonify(error=str(e)), 400

    category = str(data.get("category", "Other")).strip()
    if category not in INCOME_CATEGORIES:
        category = "Other"

    income = Income(
        user_id=user_id,
        amount=amount,
        description=description,
        category=category,
        income_date=income_date,
        is_recurring=bool(data.get("is_recurring", False)),
    )

    db.session.add(income)
    db.session.commit()

    return jsonify(income=income.to_dict()), 201


@income_bp.get("/<int:income_id>")
@jwt_required()
def get_income(income_id):
    """Get a single income record."""
    user_id = int(get_jwt_identity())
    income = Income.query.filter_by(id=income_id, user_id=user_id).first()
    if not income:
        return jsonify(error="Income record not found."), 404
    return jsonify(income=income.to_dict()), 200


@income_bp.put("/<int:income_id>")
@jwt_required()
def update_income(income_id):
    """Update an income record."""
    user_id = int(get_jwt_identity())
    income = Income.query.filter_by(id=income_id, user_id=user_id).first()
    if not income:
        return jsonify(error="Income record not found."), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    try:
        if "amount" in data:
            income.amount = validate_amount(data["amount"])
        if "description" in data:
            income.description = validate_description(data["description"])
        if "income_date" in data or "date" in data:
            income.income_date = validate_date(data.get("income_date") or data.get("date"))
    except ValueError as e:
        return jsonify(error=str(e)), 400

    if "category" in data:
        category = str(data["category"]).strip()
        if category in INCOME_CATEGORIES:
            income.category = category

    if "is_recurring" in data:
        income.is_recurring = bool(data["is_recurring"])

    db.session.commit()
    return jsonify(income=income.to_dict()), 200


@income_bp.delete("/<int:income_id>")
@jwt_required()
def delete_income(income_id):
    """Delete an income record."""
    user_id = int(get_jwt_identity())
    income = Income.query.filter_by(id=income_id, user_id=user_id).first()
    if not income:
        return jsonify(error="Income record not found."), 404

    db.session.delete(income)
    db.session.commit()
    return jsonify(deleted=True, id=income_id), 200


@income_bp.get("/categories")
@jwt_required()
def get_income_categories():
    """Get available income categories."""
    return jsonify(categories=list(INCOME_CATEGORIES)), 200

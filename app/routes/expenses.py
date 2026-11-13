"""Expense management routes."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import extract

from app.extensions import db
from app.models.expense import Expense
from app.models.category import Category
from app.services.ml_categorizer import get_categorizer, EXPENSE_CATEGORIES
from app.services.budget_service import check_and_notify_budget
from app.utils.validators import (
    validate_amount, validate_description, validate_date,
    validate_month, sanitize_string,
)

expenses_bp = Blueprint("expenses", __name__)


@expenses_bp.get("/")
@jwt_required()
def list_expenses():
    """List expenses with optional filters."""
    user_id = int(get_jwt_identity())
    month = request.args.get("month")
    category = request.args.get("category")
    search = request.args.get("search", "").strip()
    sort_by = request.args.get("sort", "date")
    order = request.args.get("order", "desc")
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 50)), 100)

    query = Expense.query.filter_by(user_id=user_id)

    if month:
        try:
            month = validate_month(month)
            year, mon = map(int, month.split("-"))
            query = query.filter(
                extract("year", Expense.expense_date) == year,
                extract("month", Expense.expense_date) == mon,
            )
        except ValueError as e:
            return jsonify(error=str(e)), 400

    if category:
        query = query.filter(Expense.category_name == category)

    if search:
        query = query.filter(
            Expense.description.ilike(f"%{search}%")
        )

    # Sorting
    if sort_by == "amount":
        order_col = Expense.amount.desc() if order == "desc" else Expense.amount.asc()
    elif sort_by == "category":
        order_col = Expense.category_name.desc() if order == "desc" else Expense.category_name.asc()
    else:
        order_col = Expense.expense_date.desc() if order == "desc" else Expense.expense_date.asc()

    paginated = query.order_by(order_col).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        expenses=[e.to_dict() for e in paginated.items],
        total=paginated.total,
        page=paginated.page,
        pages=paginated.pages,
        has_next=paginated.has_next,
    ), 200


@expenses_bp.post("/")
@jwt_required()
def create_expense():
    """Create a new expense with optional AI categorization."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    try:
        amount = validate_amount(data.get("amount"))
        description = validate_description(data.get("description"))
        expense_date = validate_date(data.get("expense_date") or data.get("date"))
        notes = sanitize_string(data.get("notes"))
    except ValueError as e:
        return jsonify(error=str(e)), 400

    # Category handling: auto-detect or user-specified
    category_name = data.get("category_name") or data.get("category")
    model_name = data.get("model", "tfidf_nb")
    predicted_category = None
    prediction_confidence = None
    user_corrected = False

    if not category_name or category_name == "Auto-detect":
        categorizer = get_categorizer()
        predicted_category, prediction_confidence = categorizer.predict(description, model_name)
        category_name = predicted_category
    else:
        user_corrected = True

    # Find category record
    cat_record = Category.get_categories_for_user(user_id, "expense")
    cat_names = [c.name for c in cat_record]
    if category_name not in cat_names:
        category_name = "Uncategorized"

    category_obj = next((c for c in cat_record if c.name == category_name), None)

    expense = Expense(
        user_id=user_id,
        amount=amount,
        description=description,
        category_id=category_obj.id if category_obj else None,
        category_name=category_name,
        expense_date=expense_date,
        predicted_category=predicted_category,
        prediction_confidence=prediction_confidence,
        prediction_model=model_name if predicted_category else None,
        user_corrected=user_corrected,
        notes=notes,
    )

    db.session.add(expense)
    db.session.commit()

    # Check budget alerts
    month_str = expense_date.strftime("%Y-%m")
    budget_alert = check_and_notify_budget(user_id, category_name, month_str)

    return jsonify(
        expense=expense.to_dict(),
        budget_alert=budget_alert,
    ), 201


@expenses_bp.get("/<int:expense_id>")
@jwt_required()
def get_expense(expense_id):
    """Get a single expense by ID."""
    user_id = int(get_jwt_identity())
    expense = Expense.query.filter_by(id=expense_id, user_id=user_id).first()
    if not expense:
        return jsonify(error="Expense not found."), 404
    return jsonify(expense=expense.to_dict()), 200


@expenses_bp.put("/<int:expense_id>")
@jwt_required()
def update_expense(expense_id):
    """Update an existing expense."""
    user_id = int(get_jwt_identity())
    expense = Expense.query.filter_by(id=expense_id, user_id=user_id).first()
    if not expense:
        return jsonify(error="Expense not found."), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    try:
        if "amount" in data:
            expense.amount = validate_amount(data["amount"])
        if "description" in data:
            expense.description = validate_description(data["description"])
        if "expense_date" in data or "date" in data:
            expense.expense_date = validate_date(data.get("expense_date") or data.get("date"))
        if "notes" in data:
            expense.notes = sanitize_string(data["notes"])
    except ValueError as e:
        return jsonify(error=str(e)), 400

    # Category update
    category_name = data.get("category_name") or data.get("category")
    if category_name:
        if category_name == "Auto-detect":
            categorizer = get_categorizer()
            predicted, confidence = categorizer.predict(expense.description, data.get("model", "tfidf_nb"))
            expense.category_name = predicted
            expense.predicted_category = predicted
            expense.prediction_confidence = confidence
            expense.user_corrected = False
        else:
            if category_name != expense.predicted_category:
                expense.user_corrected = True
            expense.category_name = category_name

    db.session.commit()
    return jsonify(expense=expense.to_dict()), 200


@expenses_bp.delete("/<int:expense_id>")
@jwt_required()
def delete_expense(expense_id):
    """Delete an expense."""
    user_id = int(get_jwt_identity())
    expense = Expense.query.filter_by(id=expense_id, user_id=user_id).first()
    if not expense:
        return jsonify(error="Expense not found."), 404

    db.session.delete(expense)
    db.session.commit()
    return jsonify(deleted=True, id=expense_id), 200


@expenses_bp.post("/predict")
@jwt_required()
def predict_category():
    """Predict category for a description using both models."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    description = str(data.get("description", "")).strip()
    if not description:
        return jsonify(error="Description cannot be empty."), 400

    categorizer = get_categorizer()
    result = categorizer.predict_both(description)

    # Add top-level category/confidence (best of tfidf_nb, fallback to keyword)
    tfidf = result.get("tfidf_nb", {})
    keyword = result.get("keyword", {})
    best_cat = tfidf.get("category") or keyword.get("category") or "Uncategorized"
    best_conf = tfidf.get("confidence") or keyword.get("confidence") or 0.0

    result["category"] = best_cat
    result["confidence"] = best_conf
    return jsonify(result), 200


@expenses_bp.get("/categories")
@jwt_required()
def get_expense_categories():
    """Get all available expense categories for current user."""
    user_id = int(get_jwt_identity())
    categories = Category.get_categories_for_user(user_id, "expense")
    return jsonify(categories=[c.to_dict() for c in categories]), 200

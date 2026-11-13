"""Recurring expense management routes."""

from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.recurring import RecurringExpense
from app.models.expense import Expense
from app.utils.validators import validate_amount, validate_description, validate_date

recurring_bp = Blueprint("recurring", __name__)


@recurring_bp.get("/")
@jwt_required()
def list_recurring():
    """List all recurring expenses."""
    user_id = int(get_jwt_identity())
    items = RecurringExpense.query.filter_by(user_id=user_id).order_by(
        RecurringExpense.next_due_date
    ).all()
    return jsonify(recurring=[item.to_dict() for item in items]), 200


@recurring_bp.post("/")
@jwt_required()
def create_recurring():
    """Create a new recurring expense."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    try:
        amount = validate_amount(data.get("amount"))
        description = validate_description(data.get("description"))
        start_date = validate_date(data.get("start_date"))
    except ValueError as e:
        return jsonify(error=str(e)), 400

    frequency = data.get("frequency", "monthly")
    if frequency not in ("weekly", "monthly", "quarterly", "yearly"):
        return jsonify(error="Frequency must be weekly, monthly, quarterly, or yearly."), 400

    category_name = str(data.get("category_name", "Bills")).strip()

    end_date = None
    if data.get("end_date"):
        try:
            end_date = validate_date(data["end_date"])
        except ValueError:
            pass

    item = RecurringExpense(
        user_id=user_id,
        description=description,
        amount=amount,
        category_name=category_name,
        frequency=frequency,
        start_date=start_date,
        end_date=end_date,
        next_due_date=start_date,
        auto_add=bool(data.get("auto_add", False)),
    )

    db.session.add(item)
    db.session.commit()

    return jsonify(recurring=item.to_dict()), 201


@recurring_bp.put("/<int:item_id>")
@jwt_required()
def update_recurring(item_id):
    """Update a recurring expense."""
    user_id = int(get_jwt_identity())
    item = RecurringExpense.query.filter_by(id=item_id, user_id=user_id).first()
    if not item:
        return jsonify(error="Recurring expense not found."), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be JSON."), 400

    try:
        if "amount" in data:
            item.amount = validate_amount(data["amount"])
        if "description" in data:
            item.description = validate_description(data["description"])
    except ValueError as e:
        return jsonify(error=str(e)), 400

    if "category_name" in data:
        item.category_name = str(data["category_name"]).strip()
    if "frequency" in data and data["frequency"] in ("weekly", "monthly", "quarterly", "yearly"):
        item.frequency = data["frequency"]
    if "is_active" in data:
        item.is_active = bool(data["is_active"])
    if "auto_add" in data:
        item.auto_add = bool(data["auto_add"])

    db.session.commit()
    return jsonify(recurring=item.to_dict()), 200


@recurring_bp.delete("/<int:item_id>")
@jwt_required()
def delete_recurring(item_id):
    """Delete a recurring expense."""
    user_id = int(get_jwt_identity())
    item = RecurringExpense.query.filter_by(id=item_id, user_id=user_id).first()
    if not item:
        return jsonify(error="Recurring expense not found."), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify(deleted=True, id=item_id), 200


@recurring_bp.post("/<int:item_id>/process")
@jwt_required()
def process_recurring(item_id):
    """Manually process a recurring expense (create the actual expense)."""
    user_id = int(get_jwt_identity())
    item = RecurringExpense.query.filter_by(id=item_id, user_id=user_id).first()
    if not item:
        return jsonify(error="Recurring expense not found."), 404

    expense = Expense(
        user_id=user_id,
        amount=item.amount,
        description=item.description,
        category_name=item.category_name,
        expense_date=item.next_due_date or date.today(),
        is_recurring=True,
    )
    db.session.add(expense)

    item.last_processed = date.today()
    item.compute_next_due()

    # Deactivate if past end_date
    if item.end_date and item.next_due_date > item.end_date:
        item.is_active = False

    db.session.commit()

    return jsonify(
        expense=expense.to_dict(),
        recurring=item.to_dict(),
    ), 201


@recurring_bp.get("/upcoming")
@jwt_required()
def upcoming_payments():
    """Get upcoming recurring payments (due within 7 days)."""
    user_id = int(get_jwt_identity())
    from datetime import timedelta
    cutoff = date.today() + timedelta(days=7)

    items = RecurringExpense.query.filter(
        RecurringExpense.user_id == user_id,
        RecurringExpense.is_active == True,
        RecurringExpense.next_due_date <= cutoff,
    ).order_by(RecurringExpense.next_due_date).all()

    return jsonify(upcoming=[item.to_dict() for item in items]), 200

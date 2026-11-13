"""Expense Split (Splitwise-style) routes."""
from datetime import datetime, date
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.split import ExpenseSplit, SplitMember
from app.utils.validators import validate_amount

splits_bp = Blueprint("splits", __name__)


@splits_bp.get("/")
@jwt_required()
def list_splits():
    """List all splits for the user."""
    user_id = int(get_jwt_identity())
    splits = ExpenseSplit.query.filter_by(user_id=user_id).order_by(ExpenseSplit.split_date.desc()).all()
    total_pending = sum(s.to_dict()["pending_to_receive"] for s in splits)
    return jsonify(splits=[s.to_dict() for s in splits], total_pending_to_receive=total_pending), 200


@splits_bp.post("/")
@jwt_required()
def create_split():
    """Create a new expense split among friends."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify(error="Title is required."), 400

    try:
        total_amount = validate_amount(data.get("total_amount"))
    except ValueError as e:
        return jsonify(error=str(e)), 400

    # Friends names list: ['Ramesh', 'Suresh', 'Priya']
    raw_friends = data.get("friends", [])
    if isinstance(raw_friends, str):
        raw_friends = [f.strip() for f in raw_friends.split(",") if f.strip()]

    # Always include 'You'
    friends_clean = ["You"] + [f for f in raw_friends if f.lower() != "you"]
    split_count = len(friends_clean)

    split_date = date.today()
    if data.get("split_date"):
        try:
            split_date = datetime.strptime(data["split_date"], "%Y-%m-%d").date()
        except ValueError:
            pass

    split = ExpenseSplit(
        user_id=user_id,
        title=title,
        total_amount=total_amount,
        split_date=split_date,
        category=str(data.get("category", "Food")),
        notes=str(data.get("notes", "")),
    )
    db.session.add(split)
    db.session.flush()

    # Per person share (equal split)
    per_person = round(total_amount / split_count, 2)

    for friend in friends_clean:
        is_you = friend.lower() == "you"
        member = SplitMember(
            split_id=split.id,
            friend_name=friend,
            share_amount=per_person,
            is_settled=is_you,  # You already paid
            settled_at=datetime.utcnow() if is_you else None,
        )
        db.session.add(member)

    db.session.commit()
    return jsonify(split=split.to_dict()), 201


@splits_bp.put("/members/<int:member_id>/toggle-settle")
@jwt_required()
def toggle_settle(member_id):
    """Mark friend's share as settled/unsettled."""
    user_id = int(get_jwt_identity())
    member = SplitMember.query.get(member_id)
    if not member or member.split.user_id != user_id:
        return jsonify(error="Member not found."), 404

    member.is_settled = not member.is_settled
    member.settled_at = datetime.utcnow() if member.is_settled else None
    db.session.commit()

    return jsonify(member=member.to_dict()), 200


@splits_bp.delete("/<int:split_id>")
@jwt_required()
def delete_split(split_id):
    """Delete a split."""
    user_id = int(get_jwt_identity())
    split = ExpenseSplit.query.filter_by(id=split_id, user_id=user_id).first()
    if not split:
        return jsonify(error="Split not found."), 404

    db.session.delete(split)
    db.session.commit()
    return jsonify(deleted=True, id=split_id), 200

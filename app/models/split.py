from datetime import datetime, date
from app.extensions import db


class ExpenseSplit(db.Model):
    __tablename__ = "expense_splits"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    split_date = db.Column(db.Date, nullable=False, default=date.today)
    category = db.Column(db.String(60), default="Food")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    members = db.relationship("SplitMember", backref="split", lazy="joined", cascade="all, delete-orphan")

    def to_dict(self):
        total = float(self.total_amount)
        member_list = [m.to_dict() for m in self.members]
        settled_count = sum(1 for m in member_list if m["is_settled"])
        pending_amount = sum(m["share_amount"] for m in member_list if not m["is_settled"] and m["friend_name"].lower() != "you")
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "total_amount": total,
            "split_date": self.split_date.isoformat() if self.split_date else None,
            "category": self.category,
            "notes": self.notes,
            "members": member_list,
            "member_count": len(member_list),
            "settled_count": settled_count,
            "is_fully_settled": settled_count == len(member_list),
            "pending_to_receive": pending_amount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SplitMember(db.Model):
    __tablename__ = "split_members"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    split_id = db.Column(db.Integer, db.ForeignKey("expense_splits.id", ondelete="CASCADE"), nullable=False, index=True)
    friend_name = db.Column(db.String(100), nullable=False)
    share_amount = db.Column(db.Numeric(12, 2), nullable=False)
    is_settled = db.Column(db.Boolean, nullable=False, default=False)
    settled_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "split_id": self.split_id,
            "friend_name": self.friend_name,
            "share_amount": float(self.share_amount),
            "is_settled": bool(self.is_settled),
            "settled_at": self.settled_at.isoformat() if self.settled_at else None,
        }

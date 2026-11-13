from datetime import datetime
from app.extensions import db


class SavingsGoal(db.Model):
    __tablename__ = "savings_goals"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    target_amount = db.Column(db.Numeric(12, 2), nullable=False)
    saved_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    target_date = db.Column(db.Date, nullable=True)
    category = db.Column(db.String(60), default="General")
    color = db.Column(db.String(20), default="#10b981")
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self):
        target = float(self.target_amount)
        saved = float(self.saved_amount)
        percentage = round((saved / target * 100), 1) if target > 0 else 0
        remaining = max(0, target - saved)
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "target_amount": target,
            "saved_amount": saved,
            "percentage": min(100.0, percentage),
            "remaining": remaining,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "category": self.category,
            "color": self.color,
            "is_completed": bool(self.is_completed) or (saved >= target),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

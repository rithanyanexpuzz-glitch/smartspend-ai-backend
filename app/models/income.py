from datetime import datetime

from app.extensions import db


class Income(db.Model):
    __tablename__ = "income"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(60), nullable=False, default="Other")
    income_date = db.Column(db.Date, nullable=False, index=True)
    is_recurring = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": float(self.amount),
            "description": self.description,
            "category": self.category,
            "income_date": self.income_date.isoformat() if self.income_date else None,
            "is_recurring": self.is_recurring,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Income {self.id}: {self.description} ₹{self.amount}>"

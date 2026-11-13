from datetime import datetime

from app.extensions import db


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    category_name = db.Column(db.String(60), nullable=False, default="Uncategorized")
    expense_date = db.Column(db.Date, nullable=False, index=True)
    predicted_category = db.Column(db.String(60), nullable=True)
    prediction_confidence = db.Column(db.Numeric(5, 4), nullable=True)
    prediction_model = db.Column(db.String(30), nullable=True)
    user_corrected = db.Column(db.Boolean, nullable=False, default=False)
    receipt_path = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_recurring = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category = db.relationship("Category", foreign_keys=[category_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": float(self.amount),
            "description": self.description,
            "category_name": self.category_name,
            "category_id": self.category_id,
            "expense_date": self.expense_date.isoformat() if self.expense_date else None,
            "predicted_category": self.predicted_category,
            "prediction_confidence": float(self.prediction_confidence) if self.prediction_confidence else None,
            "prediction_model": self.prediction_model,
            "user_corrected": self.user_corrected,
            "receipt_path": self.receipt_path,
            "notes": self.notes,
            "is_recurring": self.is_recurring,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Expense {self.id}: {self.description} ₹{self.amount}>"

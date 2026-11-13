from datetime import datetime, date, timedelta

from app.extensions import db


class RecurringExpense(db.Model):
    __tablename__ = "recurring_expenses"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    category_name = db.Column(db.String(60), nullable=False, default="Bills")
    frequency = db.Column(db.String(15), nullable=False, default="monthly")
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    next_due_date = db.Column(db.Date, nullable=False, index=True)
    last_processed = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    auto_add = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def compute_next_due(self):
        """Advance next_due_date based on frequency."""
        current = self.next_due_date or self.start_date
        if self.frequency == "weekly":
            self.next_due_date = current + timedelta(weeks=1)
        elif self.frequency == "monthly":
            month = current.month % 12 + 1
            year = current.year + (1 if current.month == 12 else 0)
            day = min(current.day, 28)
            self.next_due_date = date(year, month, day)
        elif self.frequency == "quarterly":
            month = ((current.month - 1 + 3) % 12) + 1
            year = current.year + (1 if current.month > 9 else 0)
            day = min(current.day, 28)
            self.next_due_date = date(year, month, day)
        elif self.frequency == "yearly":
            self.next_due_date = date(current.year + 1, current.month, min(current.day, 28))

    def is_due(self):
        return self.is_active and self.next_due_date <= date.today()

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "description": self.description,
            "amount": float(self.amount),
            "category_name": self.category_name,
            "frequency": self.frequency,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "next_due_date": self.next_due_date.isoformat() if self.next_due_date else None,
            "last_processed": self.last_processed.isoformat() if self.last_processed else None,
            "is_active": self.is_active,
            "auto_add": self.auto_add,
            "is_due": self.is_due(),
        }

    def __repr__(self):
        return f"<RecurringExpense {self.description} ({self.frequency})>"

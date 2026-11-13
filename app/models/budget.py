from datetime import datetime

from app.extensions import db


class Budget(db.Model):
    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_name = db.Column(db.String(60), nullable=False)
    monthly_limit = db.Column(db.Numeric(12, 2), nullable=False)
    weekly_limit = db.Column(db.Numeric(12, 2), nullable=True)
    alert_50 = db.Column(db.Boolean, nullable=False, default=True)
    alert_80 = db.Column(db.Boolean, nullable=False, default=True)
    alert_100 = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "category_name", name="uq_budget_user_cat"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "category_name": self.category_name,
            "monthly_limit": float(self.monthly_limit),
            "weekly_limit": float(self.weekly_limit) if self.weekly_limit else None,
            "alert_50": self.alert_50,
            "alert_80": self.alert_80,
            "alert_100": self.alert_100,
            "is_active": self.is_active,
        }

    def __repr__(self):
        return f"<Budget {self.category_name}: ₹{self.monthly_limit}/mo>"

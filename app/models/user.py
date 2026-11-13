from datetime import datetime

from app.extensions import db, bcrypt


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="user")
    currency = db.Column(db.String(10), nullable=False, default="INR")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    reset_token = db.Column(db.String(255), nullable=True)
    reset_token_exp = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ── Notification preferences ───────────────────────────────
    phone            = db.Column(db.String(20), nullable=True)
    notify_email     = db.Column(db.Boolean, nullable=False, default=True)
    notify_whatsapp  = db.Column(db.Boolean, nullable=False, default=False)
    whatsapp_number  = db.Column(db.String(20), nullable=True)

    # Relationships
    expenses = db.relationship("Expense", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    incomes = db.relationship("Income", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    budgets = db.relationship("Budget", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    recurring_expenses = db.relationship("RecurringExpense", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "currency": self.currency,
            "is_active": self.is_active,
            "phone": self.phone,
            "notify_email": self.notify_email,
            "notify_whatsapp": self.notify_whatsapp,
            "whatsapp_number": self.whatsapp_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<User {self.email}>"


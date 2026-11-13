from datetime import datetime

from app.extensions import db


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(60), nullable=False)
    icon = db.Column(db.String(10), default="📁")
    color = db.Column(db.String(20), default="#6b7280")
    type = db.Column(db.String(10), nullable=False, default="expense")  # expense, income, both
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("name", "user_id", name="uq_category_user"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "color": self.color,
            "type": self.type,
            "is_default": self.is_default,
        }

    @staticmethod
    def get_categories_for_user(user_id, cat_type=None):
        """Get default categories + user custom categories."""
        query = Category.query.filter(
            db.or_(Category.user_id.is_(None), Category.user_id == user_id)
        )
        if cat_type:
            query = query.filter(Category.type.in_([cat_type, "both"]))
        return query.order_by(Category.is_default.desc(), Category.name).all()

    @staticmethod
    def seed_defaults():
        """Insert default categories if they don't exist."""
        defaults = [
            # Expense categories
            ("Food", "🍔", "#2b8a70", "expense"),
            ("Transport", "🚗", "#5083b8", "expense"),
            ("Shopping", "🛍️", "#d68544", "expense"),
            ("Bills", "📄", "#8769a9", "expense"),
            ("Healthcare", "🏥", "#c75c5a", "expense"),
            ("Entertainment", "🎬", "#e0a037", "expense"),
            ("Education", "📚", "#4a90a4", "expense"),
            ("Rent", "🏠", "#7c6f57", "expense"),
            ("Insurance", "🛡️", "#5a7d9a", "expense"),
            ("Uncategorized", "📁", "#6b7280", "expense"),
            # Income categories
            ("Salary", "💰", "#2b8a70", "income"),
            ("Business", "💼", "#5083b8", "income"),
            ("Freelance", "💻", "#d68544", "income"),
            ("Investment", "📈", "#8769a9", "income"),
            ("Rental", "🏠", "#7c6f57", "income"),
            ("Other", "📁", "#6b7280", "income"),
        ]
        for name, icon, color, cat_type in defaults:
            existing = Category.query.filter_by(name=name, user_id=None, type=cat_type).first()
            if not existing:
                db.session.add(Category(
                    name=name, icon=icon, color=color,
                    type=cat_type, is_default=True, user_id=None,
                ))
        db.session.commit()

    def __repr__(self):
        return f"<Category {self.name}>"

from datetime import datetime

from app.extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(10), nullable=False, default="info")  # info, warning, alert, success
    category = db.Column(db.String(60), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    link = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "type": self.type,
            "category": self.category,
            "is_read": self.is_read,
            "link": self.link,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def create_notification(user_id, title, message, notif_type="info", category=None, link=None):
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notif_type,
            category=category,
            link=link,
        )
        db.session.add(notif)
        db.session.commit()
        return notif

    def __repr__(self):
        return f"<Notification {self.title}>"

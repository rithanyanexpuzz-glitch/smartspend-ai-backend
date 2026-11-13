from app.routes.auth import auth_bp
from app.routes.expenses import expenses_bp
from app.routes.income import income_bp
from app.routes.budgets import budgets_bp
from app.routes.dashboard import dashboard_bp
from app.routes.reports import reports_bp
from app.routes.insights import insights_bp
from app.routes.recurring import recurring_bp
from app.routes.receipts import receipts_bp
from app.routes.notifications import notifications_bp
from app.routes.goals import goals_bp
from app.routes.advisor import advisor_bp
from app.routes.splits import splits_bp


def register_routes(app):
    """Register all API blueprints."""
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(expenses_bp, url_prefix="/api/expenses")
    app.register_blueprint(income_bp, url_prefix="/api/income")
    app.register_blueprint(budgets_bp, url_prefix="/api/budgets")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")
    app.register_blueprint(insights_bp, url_prefix="/api/insights")
    app.register_blueprint(recurring_bp, url_prefix="/api/recurring")
    app.register_blueprint(receipts_bp, url_prefix="/api/receipts")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(goals_bp, url_prefix="/api/goals")
    app.register_blueprint(advisor_bp, url_prefix="/api/advisor")
    app.register_blueprint(splits_bp, url_prefix="/api/splits")

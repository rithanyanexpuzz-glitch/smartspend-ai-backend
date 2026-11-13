"""SmartSpend AI - Flask Application Factory."""

import os
from flask import Flask, jsonify
from flask_jwt_extended import exceptions as jwt_exceptions

from app.config import config_by_name
from app.extensions import db, jwt, bcrypt, cors, migrate


def create_app(config_name=None):
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.url_map.strict_slashes = False
    app.config.from_object(config_by_name.get(config_name, config_by_name["development"]))
    app.json.sort_keys = False

    # ── Initialize extensions ─────────────────────────────────
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={
        r"/api/*": {
            "origins": [
                app.config.get("FRONTEND_URL", "http://localhost:5173"),
                "http://localhost:3000",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:3000",
            ],
            "supports_credentials": True,
        }
    })

    # ── Register blueprints ───────────────────────────────────
    from app.routes import register_routes
    register_routes(app)

    # ── Import models so they are registered with SQLAlchemy ──
    from app.models import (  # noqa: F401
        User, Category, Expense, Income, Budget,
        RecurringExpense, Notification,
    )

    # ── Create tables and seed defaults ───────────────────────
    with app.app_context():
        db.create_all()
        Category.seed_defaults()

    # ── JWT error handlers ────────────────────────────────────
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify(error="Token has expired.", code="token_expired"), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error_msg):
        return jsonify(error="Invalid token.", code="token_invalid"), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error_msg):
        return jsonify(error="Authentication required.", code="authorization_required"), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify(error="Token has been revoked.", code="token_revoked"), 401

    # ── Global error handlers ─────────────────────────────────
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify(error="Bad request."), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify(error="Resource not found."), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify(error="Method not allowed."), 405

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify(error="Internal server error."), 500

    # ── Health check ──────────────────────────────────────────
    @app.get("/api/health")
    def health():
        return jsonify(status="ok", app="SmartSpend AI"), 200

    return app

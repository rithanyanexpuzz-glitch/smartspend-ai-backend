"""AI Financial Insights routes."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.insights_service import get_ai_insights
from app.services.ml_categorizer import get_categorizer

insights_bp = Blueprint("insights", __name__)


@insights_bp.get("/")
@jwt_required()
def get_insights():
    """Get AI-generated financial insights."""
    user_id = int(get_jwt_identity())
    insights = get_ai_insights(user_id)
    return jsonify(insights=insights), 200


@insights_bp.get("/models/evaluate")
@jwt_required()
def evaluate_models():
    """Evaluate ML models on held-out test data."""
    categorizer = get_categorizer()
    results = categorizer.evaluate()
    return jsonify(models=results), 200

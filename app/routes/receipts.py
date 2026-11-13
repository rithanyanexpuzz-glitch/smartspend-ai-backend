"""Receipt scanning routes."""

import os
from pathlib import Path
from werkzeug.utils import secure_filename

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

receipts_bp = Blueprint("receipts", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@receipts_bp.post("/scan")
@jwt_required()
def scan_receipt():
    """Upload and scan a receipt image."""
    if "file" not in request.files:
        return jsonify(error="No file uploaded. Send file in 'file' field."), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify(error="No file selected."), 400

    if not _allowed_file(file.filename):
        return jsonify(error=f"Allowed file types: {', '.join(ALLOWED_EXTENSIONS)}"), 400

    # Save file
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    user_id = get_jwt_identity()
    filename = secure_filename(f"receipt_{user_id}_{file.filename}")
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)

    # Run OCR
    try:
        from app.services.ocr_service import scan_receipt as do_scan
        result = do_scan(filepath)
    except ImportError as e:
        return jsonify(
            error=str(e),
            message="OCR dependencies not installed. Install pytesseract and Pillow.",
        ), 500
    except Exception as e:
        return jsonify(error=f"Receipt scanning failed: {str(e)}"), 500

    result["file_path"] = filepath
    return jsonify(result), 200

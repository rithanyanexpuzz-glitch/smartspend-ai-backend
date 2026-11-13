"""OCR Receipt Scanner Service."""

import os
import re
from pathlib import Path
from datetime import date


def scan_receipt(image_path):
    """
    Extract text from receipt image using Tesseract OCR.
    Returns extracted shop name, date, amount, and suggested category.

    Requires: pip install pytesseract Pillow
    And Tesseract OCR installed on the system.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError(
            "pytesseract and Pillow are required for receipt scanning. "
            "Install: pip install pytesseract Pillow\n"
            "Also install Tesseract OCR: https://github.com/tesseract-ocr/tesseract"
        )

    tesseract_cmd = os.getenv("TESSERACT_CMD", "tesseract")
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
    except Exception as e:
        return {
            "success": False,
            "error": f"OCR extraction failed: {str(e)}",
            "raw_text": "",
        }

    return _parse_receipt_text(text)


def _parse_receipt_text(text):
    """Parse OCR text to extract receipt details."""
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]

    if not lines:
        return {
            "success": False,
            "error": "No text could be extracted from the image.",
            "raw_text": text,
        }

    # Shop name: usually the first non-empty, non-numeric line
    shop_name = ""
    for line in lines[:5]:
        cleaned = re.sub(r"[^a-zA-Z\s]", "", line).strip()
        if len(cleaned) > 2:
            shop_name = cleaned
            break

    # Date extraction: look for common date patterns
    receipt_date = None
    date_patterns = [
        r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})",  # DD/MM/YYYY or MM/DD/YYYY
        r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})",  # YYYY-MM-DD
        r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                groups = match.groups()
                if len(groups[0]) == 4:  # YYYY-MM-DD
                    receipt_date = f"{groups[0]}-{int(groups[1]):02d}-{int(groups[2]):02d}"
                else:
                    receipt_date = f"{groups[2]}-{int(groups[1]):02d}-{int(groups[0]):02d}"
            except (ValueError, IndexError):
                pass
            break

    if not receipt_date:
        receipt_date = date.today().isoformat()

    # Amount extraction: look for total/grand total patterns
    amount = 0.0
    amount_patterns = [
        r"(?:total|grand\s*total|amount|net\s*total|balance\s*due)[:\s]*[₹$]?\s*([\d,]+\.?\d*)",
        r"[₹$]\s*([\d,]+\.\d{2})",
        r"([\d,]+\.\d{2})\s*(?:total|due|amount)",
    ]
    for pattern in amount_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                amount = float(match.group(1).replace(",", ""))
                break
            except ValueError:
                continue

    # If no total found, take the largest number
    if amount == 0:
        numbers = re.findall(r"[\d,]+\.\d{2}", text)
        if numbers:
            try:
                amount = max(float(n.replace(",", "")) for n in numbers)
            except ValueError:
                pass

    # Category suggestion based on text content
    from app.services.ml_categorizer import KeywordRuleClassifier
    classifier = KeywordRuleClassifier()
    suggested_category = classifier.predict(text)

    return {
        "success": True,
        "shop_name": shop_name or "Unknown",
        "date": receipt_date,
        "amount": amount,
        "suggested_category": suggested_category,
        "raw_text": text,
        "confidence": "high" if (shop_name and amount > 0) else "low",
    }

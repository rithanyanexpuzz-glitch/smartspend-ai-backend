"""Input validation helpers."""

import re
import math
from datetime import date


def validate_amount(value, field_name="Amount"):
    """Validate a monetary amount."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid number.")
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError(f"{field_name} must be a positive finite number.")
    if amount > 99999999.99:
        raise ValueError(f"{field_name} cannot exceed ₹99,999,999.99.")
    return round(amount, 2)


def validate_description(value, max_length=255):
    """Validate a text description."""
    if not value or not str(value).strip():
        raise ValueError("Description cannot be empty.")
    value = str(value).strip()
    if len(value) > max_length:
        raise ValueError(f"Description must be {max_length} characters or fewer.")
    return value


def validate_date(value, field_name="Date"):
    """Validate a date string in YYYY-MM-DD format."""
    if not value:
        return date.today()
    try:
        parsed = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid date in YYYY-MM-DD format.")
    if parsed.isoformat() != str(value):
        raise ValueError(f"{field_name} must be a valid date in YYYY-MM-DD format.")
    return parsed


def validate_month(value):
    """Validate a month string in YYYY-MM format."""
    if not value:
        return date.today().strftime("%Y-%m")
    value = str(value)
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError("Month must be in YYYY-MM format.")
    try:
        date.fromisoformat(f"{value}-01")
    except ValueError:
        raise ValueError("Month must be a valid month in YYYY-MM format.")
    return value


def validate_email(value):
    """Validate email format."""
    if not value or not str(value).strip():
        raise ValueError("Email is required.")
    value = str(value).strip().lower()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, value):
        raise ValueError("Please enter a valid email address.")
    return value


def validate_password(value):
    """Validate password strength."""
    if not value or len(str(value)) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    password = str(value)
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one digit.")
    return password


def validate_category(value, allowed_categories):
    """Validate category is in allowed list."""
    if not value:
        return None
    value = str(value).strip()
    if value == "Auto-detect":
        return None
    if value not in allowed_categories:
        raise ValueError(f"Category must be one of: {', '.join(allowed_categories)}")
    return value


def sanitize_string(value, max_length=500):
    """Sanitize user input string."""
    if value is None:
        return None
    value = str(value).strip()
    # Remove potential script injection
    value = re.sub(r"<[^>]*>", "", value)
    return value[:max_length]

import hmac

from flask import current_app, request


def admin_authorized() -> bool:
    expected = current_app.config.get("ADMIN_API_KEY", "")
    supplied = request.headers.get("X-API-Key", "")
    return bool(expected) and hmac.compare_digest(supplied, expected)

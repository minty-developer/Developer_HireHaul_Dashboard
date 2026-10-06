import hmac

from flask import current_app, jsonify, request

from . import bp
from ..feed_collector import CollectionError, collect_all, collect_blog


def _authorized() -> bool:
    expected = current_app.config.get("ADMIN_API_KEY", "")
    supplied = request.headers.get("X-API-Key", "")
    return bool(expected) and hmac.compare_digest(supplied, expected)


@bp.post("/api/admin/sync")
def sync_all_blogs():
    if not _authorized():
        return jsonify({"ok": False, "error": "인증에 실패했습니다."}), 401

    result = collect_all(current_app.config["DATABASE_PATH"])
    return jsonify({"ok": result["failed"] == 0, **result})


@bp.post("/api/admin/sync/<int:blog_id>")
def sync_one_blog(blog_id: int):
    if not _authorized():
        return jsonify({"ok": False, "error": "인증에 실패했습니다."}), 401

    try:
        result = collect_blog(current_app.config["DATABASE_PATH"], blog_id)
    except LookupError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404
    except CollectionError as exc:
        current_app.logger.warning("Blog collection failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 502

    return jsonify({"ok": True, **result})

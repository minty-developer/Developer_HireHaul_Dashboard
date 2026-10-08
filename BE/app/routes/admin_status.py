from pathlib import Path

from flask import current_app, jsonify

from app.admin_auth import admin_authorized
from app.db import connect

from . import bp


@bp.get("/api/admin/status")
def admin_status():
    if not admin_authorized():
        return jsonify({"ok": False, "error": "관리자 인증에 실패했습니다."}), 401
    database_path = current_app.config["DATABASE_PATH"]
    with connect(database_path) as db:
        counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("blogs", "articles", "users", "subscriptions")
        }
        sync = db.execute(
            """
            SELECT MAX(last_checked_at) AS last_checked_at,
                   MAX(last_success_at) AS last_success_at,
                   SUM(CASE WHEN last_error IS NOT NULL THEN 1 ELSE 0 END) AS failed_blogs
            FROM blogs
            """
        ).fetchone()
    return jsonify({
        "status": "ok",
        "database_size_bytes": Path(database_path).stat().st_size,
        "counts": counts,
        "sync": dict(sync),
    })

import sqlite3

from flask import current_app, jsonify

from . import bp
from ..db import connect


@bp.get("/api/health")
def health():
    try:
        with connect(current_app.config["DATABASE_PATH"]) as db:
            db.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        current_app.logger.exception("Database health check failed")
        return jsonify({"status": "error", "database": "unavailable"}), 503

    return jsonify({"status": "ok", "database": "ok"})

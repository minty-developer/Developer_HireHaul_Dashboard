from flask import current_app, jsonify

from . import bp
from ..db import connect


@bp.get("/api/stats")
def stats():

    active_clause = (
        "active = 1 AND "
        "(expires_at IS NULL OR expires_at = '' OR datetime(expires_at) >= datetime('now'))"
    )

    with connect(current_app.config["DATABASE_PATH"]) as db:

        total = db.execute(
            f"SELECT COUNT(*) FROM jobs WHERE {active_clause}"
        ).fetchone()[0]

        companies = db.execute(
            f"SELECT COUNT(DISTINCT company) FROM jobs WHERE {active_clause}"
        ).fetchone()[0]

        sources = [
            dict(row)
            for row in db.execute(
                """
                SELECT source, COUNT(*) AS count
                FROM jobs
                WHERE active = 1
                  AND (expires_at IS NULL OR expires_at = '' OR datetime(expires_at) >= datetime('now'))
                GROUP BY source
                """
            ).fetchall()
        ]

    return jsonify({
        "total": total,
        "companies": companies,
        "sources": sources
    })

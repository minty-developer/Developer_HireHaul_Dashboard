from flask import current_app, jsonify

from . import bp
from ..db import connect


@bp.get("/api/stats")
def stats():

    with connect(current_app.config["DATABASE_PATH"]) as db:

        total = db.execute(
            "SELECT COUNT(*) FROM jobs WHERE active = 1"
        ).fetchone()[0]

        companies = db.execute(
            "SELECT COUNT(DISTINCT company) FROM jobs WHERE active = 1"
        ).fetchone()[0]

        sources = [
            dict(row)
            for row in db.execute(
                """
                SELECT source, COUNT(*) AS count
                FROM jobs
                WHERE active = 1
                GROUP BY source
                """
            ).fetchall()
        ]

    return jsonify({
        "total": total,
        "companies": companies,
        "sources": sources
    })
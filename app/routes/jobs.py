from flask import current_app, jsonify, request

from . import bp
from ..db import connect


@bp.get("/api/jobs")
def jobs():

    keyword = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    source = request.args.get("source", "").strip()

    limit = min(
        max(request.args.get("limit", 50, type=int), 1),
        200
    )

    clauses = ["active = 1"]
    values = []

    if keyword:
        clauses.append(
            "(title LIKE ? OR company LIKE ? OR keywords LIKE ?)"
        )

        values.extend([
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%"
        ])

    if location:
        clauses.append("location LIKE ?")
        values.append(f"%{location}%")

    if source:
        clauses.append("source = ?")
        values.append(source)

    sql = f"""
        SELECT *
        FROM jobs
        WHERE {' AND '.join(clauses)}
        ORDER BY posted_at DESC
        LIMIT ?
    """

    values.append(limit)

    with connect(current_app.config["DATABASE_PATH"]) as db:

        rows = [
            dict(row)
            for row in db.execute(sql, values).fetchall()
        ]

    return jsonify({
        "count": len(rows),
        "jobs": rows
    })
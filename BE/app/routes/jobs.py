from flask import current_app, jsonify, request

from . import bp
from ..db import connect


@bp.get("/api/jobs")
def jobs():

    keyword = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    source = request.args.get("source", "").strip()

    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "limit과 offset은 정수여야 합니다."}), 400

    if not 1 <= limit <= 200 or offset < 0:
        return jsonify({
            "ok": False,
            "error": "limit은 1~200, offset은 0 이상이어야 합니다."
        }), 400

    clauses = [
        "active = 1",
        "(expires_at IS NULL OR expires_at = '' OR datetime(expires_at) >= datetime('now'))"
    ]
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
        LIMIT ? OFFSET ?
    """

    query_values = [*values, limit, offset]

    with connect(current_app.config["DATABASE_PATH"]) as db:

        total = db.execute(
            f"SELECT COUNT(*) FROM jobs WHERE {' AND '.join(clauses)}",
            values
        ).fetchone()[0]

        rows = [
            dict(row)
            for row in db.execute(sql, query_values).fetchall()
        ]

    return jsonify({
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "jobs": rows
    })

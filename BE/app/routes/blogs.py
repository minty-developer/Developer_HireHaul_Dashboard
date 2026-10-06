from flask import current_app, jsonify

from . import bp
from ..db import connect


@bp.get("/api/blogs")
def blogs():
    with connect(current_app.config["DATABASE_PATH"]) as db:
        rows = db.execute(
            """
            SELECT
                b.id, b.name, b.company, b.feed_url, b.site_url,
                b.description, b.last_checked_at, b.last_success_at,
                COUNT(a.id) AS article_count
            FROM blogs b
            LEFT JOIN articles a ON a.blog_id = b.id
            WHERE b.active = 1
            GROUP BY b.id
            ORDER BY b.company, b.name
            """
        ).fetchall()

    return jsonify({
        "count": len(rows),
        "blogs": [dict(row) for row in rows],
    })


@bp.get("/api/blogs/<int:blog_id>")
def blog_detail(blog_id: int):
    with connect(current_app.config["DATABASE_PATH"]) as db:
        row = db.execute(
            """
            SELECT
                b.id, b.name, b.company, b.feed_url, b.site_url,
                b.description, b.last_checked_at, b.last_success_at,
                COUNT(a.id) AS article_count
            FROM blogs b
            LEFT JOIN articles a ON a.blog_id = b.id
            WHERE b.id = ? AND b.active = 1
            GROUP BY b.id
            """,
            (blog_id,),
        ).fetchone()

    if row is None:
        return jsonify({"ok": False, "error": "블로그를 찾을 수 없습니다."}), 404
    return jsonify({"blog": dict(row)})

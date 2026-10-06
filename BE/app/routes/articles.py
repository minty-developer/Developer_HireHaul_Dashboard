from datetime import date

from flask import current_app, jsonify, request

from . import bp
from ..db import connect


def _pagination() -> tuple[int, int] | tuple[None, None]:
    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return None, None
    if not 1 <= limit <= 100 or offset < 0:
        return None, None
    return limit, offset


def _date_filter(name: str) -> str | None:
    value = request.args.get(name, "").strip()
    if not value:
        return ""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


@bp.get("/api/articles")
def articles():
    limit, offset = _pagination()
    if limit is None:
        return jsonify({
            "ok": False,
            "error": "limit은 1~100, offset은 0 이상의 정수여야 합니다.",
        }), 400

    query = request.args.get("q", "").strip()
    if len(query) > 200:
        return jsonify({"ok": False, "error": "검색어는 200자 이하여야 합니다."}), 400

    try:
        blog_id = int(request.args["blog_id"]) if request.args.get("blog_id") else None
    except ValueError:
        return jsonify({"ok": False, "error": "blog_id는 정수여야 합니다."}), 400
    if blog_id is not None and blog_id < 1:
        return jsonify({"ok": False, "error": "blog_id는 1 이상이어야 합니다."}), 400

    date_from = _date_filter("from")
    date_to = _date_filter("to")
    if date_from is None or date_to is None:
        return jsonify({"ok": False, "error": "날짜는 YYYY-MM-DD 형식이어야 합니다."}), 400
    if date_from and date_to and date_from > date_to:
        return jsonify({"ok": False, "error": "from은 to보다 늦을 수 없습니다."}), 400

    clauses = ["b.active = 1"]
    values: list[object] = []
    if query:
        clauses.append(
            "(a.title LIKE ? OR a.summary LIKE ? OR a.content LIKE ? OR a.author LIKE ?)"
        )
        pattern = f"%{query}%"
        values.extend([pattern, pattern, pattern, pattern])
    if blog_id is not None:
        clauses.append("a.blog_id = ?")
        values.append(blog_id)
    if date_from:
        clauses.append("date(a.published_at) >= date(?)")
        values.append(date_from)
    if date_to:
        clauses.append("date(a.published_at) <= date(?)")
        values.append(date_to)

    where = " AND ".join(clauses)
    database_path = current_app.config["DATABASE_PATH"]
    with connect(database_path) as db:
        total = db.execute(
            f"""SELECT COUNT(*) FROM articles a
                JOIN blogs b ON b.id = a.blog_id
                WHERE {where}""",
            values,
        ).fetchone()[0]
        rows = db.execute(
            f"""
            SELECT
                a.id, a.blog_id, a.entry_key, a.title, a.url, a.author,
                a.summary, a.published_at, a.feed_updated_at, a.fetched_at,
                b.name AS blog_name, b.company
            FROM articles a
            JOIN blogs b ON b.id = a.blog_id
            WHERE {where}
            ORDER BY COALESCE(a.published_at, a.fetched_at) DESC, a.id DESC
            LIMIT ? OFFSET ?
            """,
            [*values, limit, offset],
        ).fetchall()

    return jsonify({
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "articles": [dict(row) for row in rows],
    })


@bp.get("/api/articles/<int:article_id>")
def article_detail(article_id: int):
    with connect(current_app.config["DATABASE_PATH"]) as db:
        row = db.execute(
            """
            SELECT
                a.*, b.name AS blog_name, b.company,
                b.site_url AS blog_site_url
            FROM articles a
            JOIN blogs b ON b.id = a.blog_id
            WHERE a.id = ? AND b.active = 1
            """,
            (article_id,),
        ).fetchone()

    if row is None:
        return jsonify({"ok": False, "error": "게시글을 찾을 수 없습니다."}), 404
    return jsonify({"article": dict(row)})

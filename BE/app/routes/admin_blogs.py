from __future__ import annotations

import sqlite3
from urllib.parse import urlparse

from flask import current_app, jsonify, request

from app.admin_auth import admin_authorized
from app.db import connect, upsert_blog

from . import bp


def _unauthorized():
    return jsonify({"ok": False, "error": "관리자 인증에 실패했습니다."}), 401


def _valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _blog_values(body: dict, *, partial: bool = False) -> tuple[dict | None, str | None]:
    fields = ("name", "company", "feed_url", "site_url", "description", "active")
    values = {field: body[field] for field in fields if field in body}
    required = ("name", "company", "feed_url", "site_url")
    if not partial and any(field not in values for field in required):
        return None, "name, company, feed_url, site_url은 필수입니다."

    for field in ("name", "company"):
        if field in values:
            values[field] = str(values[field]).strip()
            if not values[field] or len(values[field]) > 100:
                return None, f"{field}은 1~100자여야 합니다."
    if "description" in values:
        values["description"] = str(values["description"]).strip()
        if len(values["description"]) > 1000:
            return None, "description은 1000자 이하여야 합니다."
    for field in ("feed_url", "site_url"):
        if field in values:
            values[field] = str(values[field]).strip()
            if len(values[field]) > 2048 or not _valid_url(values[field]):
                return None, f"올바른 {field}을 입력해주세요."
    if "active" in values:
        if not isinstance(values["active"], bool):
            return None, "active는 boolean이어야 합니다."
        values["active"] = int(values["active"])
    return values, None


@bp.get("/api/admin/blogs")
def admin_blogs():
    if not admin_authorized():
        return _unauthorized()
    with connect(current_app.config["DATABASE_PATH"]) as db:
        rows = db.execute(
            """
            SELECT b.*, COUNT(a.id) AS article_count
            FROM blogs b
            LEFT JOIN articles a ON a.blog_id = b.id
            GROUP BY b.id
            ORDER BY b.company, b.name
            """
        ).fetchall()
    return jsonify({"count": len(rows), "blogs": [dict(row) for row in rows]})


@bp.post("/api/admin/blogs")
def create_admin_blog():
    if not admin_authorized():
        return _unauthorized()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "JSON 요청 본문이 필요합니다."}), 400
    values, error = _blog_values(body)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    with connect(current_app.config["DATABASE_PATH"]) as db:
        existing = db.execute(
            "SELECT id FROM blogs WHERE feed_url = ?", (values["feed_url"],)
        ).fetchone()
    if existing:
        return jsonify({"ok": False, "error": "이미 등록된 피드 URL입니다."}), 409
    try:
        blog_id = upsert_blog(current_app.config["DATABASE_PATH"], values)
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "블로그를 저장할 수 없습니다."}), 409
    with connect(current_app.config["DATABASE_PATH"]) as db:
        row = db.execute("SELECT * FROM blogs WHERE id = ?", (blog_id,)).fetchone()
    return jsonify({"blog": dict(row)}), 201


@bp.patch("/api/admin/blogs/<int:blog_id>")
def update_admin_blog(blog_id: int):
    if not admin_authorized():
        return _unauthorized()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "JSON 요청 본문이 필요합니다."}), 400
    values, error = _blog_values(body, partial=True)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    if not values:
        return jsonify({"ok": False, "error": "수정할 필드가 없습니다."}), 400

    assignments = ", ".join(f"{field} = ?" for field in values)
    try:
        with connect(current_app.config["DATABASE_PATH"]) as db:
            cursor = db.execute(
                f"UPDATE blogs SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [*values.values(), blog_id],
            )
            row = db.execute("SELECT * FROM blogs WHERE id = ?", (blog_id,)).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "이미 등록된 피드 URL입니다."}), 409
    if cursor.rowcount == 0:
        return jsonify({"ok": False, "error": "블로그를 찾을 수 없습니다."}), 404
    return jsonify({"blog": dict(row)})


@bp.delete("/api/admin/blogs/<int:blog_id>")
def deactivate_admin_blog(blog_id: int):
    if not admin_authorized():
        return _unauthorized()
    with connect(current_app.config["DATABASE_PATH"]) as db:
        cursor = db.execute(
            "UPDATE blogs SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (blog_id,),
        )
    if cursor.rowcount == 0:
        return jsonify({"ok": False, "error": "블로그를 찾을 수 없습니다."}), 404
    return "", 204

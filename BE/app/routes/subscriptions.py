from __future__ import annotations

import sqlite3

from flask import current_app, jsonify, request

from app.auth import require_user
from app.db import connect

from . import bp


@bp.get("/api/subscriptions")
def subscriptions():
    user, error = require_user()
    if error:
        return jsonify(error[0]), error[1]

    with connect(current_app.config["DATABASE_PATH"]) as db:
        rows = db.execute(
            """
            SELECT id, keyword, active, created_at, updated_at
            FROM subscriptions
            WHERE user_id = ?
            ORDER BY keyword COLLATE NOCASE, id
            """,
            (user["id"],),
        ).fetchall()
    return jsonify({"subscriptions": [dict(row) for row in rows]})


@bp.post("/api/subscriptions")
def create_subscription():
    user, error = require_user()
    if error:
        return jsonify(error[0]), error[1]

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "JSON 요청 본문이 필요합니다."}), 400
    keyword = " ".join(str(body.get("keyword", "")).split())
    if not keyword or len(keyword) > 100:
        return jsonify({"error": "키워드는 1~100자여야 합니다."}), 400

    try:
        with connect(current_app.config["DATABASE_PATH"]) as db:
            cursor = db.execute(
                "INSERT INTO subscriptions (user_id, keyword) VALUES (?, ?)",
                (user["id"], keyword),
            )
            row = db.execute(
                """
                SELECT id, keyword, active, created_at, updated_at
                FROM subscriptions WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "이미 구독 중인 키워드입니다."}), 409
    return jsonify({"subscription": dict(row)}), 201


@bp.delete("/api/subscriptions/<int:subscription_id>")
def delete_subscription(subscription_id: int):
    user, error = require_user()
    if error:
        return jsonify(error[0]), error[1]

    with connect(current_app.config["DATABASE_PATH"]) as db:
        cursor = db.execute(
            "DELETE FROM subscriptions WHERE id = ? AND user_id = ?",
            (subscription_id, user["id"]),
        )
    if cursor.rowcount == 0:
        return jsonify({"error": "구독을 찾을 수 없습니다."}), 404
    return "", 204

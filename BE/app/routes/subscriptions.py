from __future__ import annotations

import sqlite3

from flask import current_app, jsonify, request

from app.auth import require_user
from app.db import connect
from app.discord_webhook import valid_discord_webhook_url

from . import bp


@bp.get("/api/subscriptions")
def subscriptions():
    user, error = require_user()
    if error:
        return jsonify(error[0]), error[1]

    with connect(current_app.config["DATABASE_PATH"]) as db:
        rows = db.execute(
            """
            SELECT id, keyword, discord_webhook_url, active, created_at, updated_at
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
    webhook_url = str(body.get("discord_webhook_url", "")).strip() or None
    if webhook_url and not valid_discord_webhook_url(webhook_url):
        return jsonify({"error": "유효한 Discord 웹훅 URL이 아닙니다."}), 400

    try:
        with connect(current_app.config["DATABASE_PATH"]) as db:
            cursor = db.execute(
                """INSERT INTO subscriptions
                    (user_id, keyword, discord_webhook_url) VALUES (?, ?, ?)""",
                (user["id"], keyword, webhook_url),
            )
            row = db.execute(
                """
                SELECT id, keyword, discord_webhook_url, active, created_at, updated_at
                FROM subscriptions WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "이미 구독 중인 키워드입니다."}), 409
    return jsonify({"subscription": dict(row)}), 201


@bp.patch("/api/subscriptions/<int:subscription_id>")
def update_subscription(subscription_id: int):
    user, error = require_user()
    if error:
        return jsonify(error[0]), error[1]

    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not ({"discord_webhook_url", "active"} & body.keys()):
        return jsonify({"error": "discord_webhook_url 또는 active가 필요합니다."}), 400

    updates = []
    values = []
    if "discord_webhook_url" in body:
        supplied_url = body["discord_webhook_url"]
        if supplied_url is not None and not isinstance(supplied_url, str):
            return jsonify({"error": "유효한 Discord 웹훅 URL이 아닙니다."}), 400
        webhook_url = supplied_url.strip() if supplied_url else None
        if webhook_url and not valid_discord_webhook_url(webhook_url):
            return jsonify({"error": "유효한 Discord 웹훅 URL이 아닙니다."}), 400
        updates.append("discord_webhook_url = ?")
        values.append(webhook_url)
    if "active" in body:
        if not isinstance(body["active"], bool):
            return jsonify({"error": "active는 boolean이어야 합니다."}), 400
        updates.append("active = ?")
        values.append(int(body["active"]))

    with connect(current_app.config["DATABASE_PATH"]) as db:
        cursor = db.execute(
            f"""
            UPDATE subscriptions
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (*values, subscription_id, user["id"]),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "구독을 찾을 수 없습니다."}), 404
        row = db.execute(
            """
            SELECT id, keyword, discord_webhook_url, active, created_at, updated_at
            FROM subscriptions WHERE id = ?
            """,
            (subscription_id,),
        ).fetchone()
    return jsonify({"subscription": dict(row)})


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

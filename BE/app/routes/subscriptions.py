from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Response

from ..db import connect
from ..deps import CurrentUser, DatabasePath
from ..errors import ApiError
from ..schemas import SubscriptionCreateRequest, SubscriptionUpdateRequest

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

COLUMNS = "id, keyword, discord_webhook_url, active, created_at, updated_at"


@router.get("", summary="내 키워드 구독 목록")
def list_subscriptions(user: CurrentUser, database_path: DatabasePath):
    with connect(database_path) as db:
        rows = db.execute(
            f"""
            SELECT {COLUMNS} FROM subscriptions
            WHERE user_id = ?
            ORDER BY keyword COLLATE NOCASE, id
            """,
            (user["id"],),
        ).fetchall()
    return {"subscriptions": [dict(row) for row in rows]}


@router.post("", status_code=201, summary="키워드 구독 추가")
def create_subscription(
    body: SubscriptionCreateRequest, user: CurrentUser, database_path: DatabasePath
):
    try:
        with connect(database_path) as db:
            cursor = db.execute(
                "INSERT INTO subscriptions (user_id, keyword, discord_webhook_url) VALUES (?, ?, ?)",
                (user["id"], body.keyword, body.discord_webhook_url),
            )
            row = db.execute(
                f"SELECT {COLUMNS} FROM subscriptions WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
    except sqlite3.IntegrityError:
        raise ApiError(409, "이미 구독 중인 키워드입니다.") from None
    return {"subscription": dict(row)}


@router.patch(
    "/{subscription_id}",
    summary="Discord 웹훅 주소 및 활성 상태 변경",
    description="보낸 필드만 변경합니다. `discord_webhook_url: null`은 알림을 끕니다.",
)
def update_subscription(
    subscription_id: int,
    body: SubscriptionUpdateRequest,
    user: CurrentUser,
    database_path: DatabasePath,
):
    provided = body.model_fields_set
    if not provided & {"discord_webhook_url", "active"}:
        raise ApiError(400, "discord_webhook_url 또는 active가 필요합니다.")

    updates, values = [], []
    if "discord_webhook_url" in provided:
        updates.append("discord_webhook_url = ?")
        values.append(body.discord_webhook_url)
    if "active" in provided:
        if body.active is None:
            raise ApiError(400, "active는 boolean이어야 합니다.")
        updates.append("active = ?")
        values.append(int(body.active))

    with connect(database_path) as db:
        cursor = db.execute(
            f"""
            UPDATE subscriptions
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (*values, subscription_id, user["id"]),
        )
        if cursor.rowcount == 0:
            raise ApiError(404, "구독을 찾을 수 없습니다.")
        row = db.execute(
            f"SELECT {COLUMNS} FROM subscriptions WHERE id = ?", (subscription_id,)
        ).fetchone()
    return {"subscription": dict(row)}


@router.delete("/{subscription_id}", status_code=204, summary="키워드 구독 삭제")
def delete_subscription(subscription_id: int, user: CurrentUser, database_path: DatabasePath):
    with connect(database_path) as db:
        cursor = db.execute(
            "DELETE FROM subscriptions WHERE id = ? AND user_id = ?",
            (subscription_id, user["id"]),
        )
    if cursor.rowcount == 0:
        raise ApiError(404, "구독을 찾을 수 없습니다.")
    return Response(status_code=204)

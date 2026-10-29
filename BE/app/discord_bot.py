from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from .db import connect


DISCORD_API = "https://discord.com/api/v10"
EPHEMERAL = 64

COMMANDS = [
    {
        "name": "알림채널",
        "description": "기술 블로그 알림을 받을 채널을 설정합니다.",
        "options": [{
            "name": "channel",
            "description": "알림 채널",
            "type": 7,
            "required": True,
        }],
        "default_member_permissions": "32",
        "contexts": [0],
        "integration_types": [0],
    },
    {
        "name": "구독추가",
        "description": "현재 서버에 키워드 구독을 추가합니다.",
        "options": [{
            "name": "keyword",
            "description": "알림 받을 키워드",
            "type": 3,
            "required": True,
        }],
        "contexts": [0],
        "integration_types": [0],
    },
    {"name": "구독목록", "description": "현재 서버의 키워드 구독을 조회합니다.", "contexts": [0], "integration_types": [0]},
    {
        "name": "구독삭제",
        "description": "현재 서버의 키워드 구독을 삭제합니다.",
        "options": [{
            "name": "keyword",
            "description": "삭제할 키워드",
            "type": 3,
            "required": True,
        }],
        "contexts": [0],
        "integration_types": [0],
    },
    {
        "name": "최신글",
        "description": "최근 기술 블로그 글을 조회합니다.",
        "options": [{"name": "count", "description": "조회 개수(1~10)", "type": 4}],
        "contexts": [0],
        "integration_types": [0],
    },
    {
        "name": "검색",
        "description": "수집된 기술 블로그 글을 검색합니다.",
        "options": [{
            "name": "keyword",
            "description": "검색어",
            "type": 3,
            "required": True,
        }],
        "contexts": [0],
        "integration_types": [0],
    },
]


def verify_interaction(public_key: str, signature: str, timestamp: str, body: bytes) -> bool:
    try:
        VerifyKey(bytes.fromhex(public_key)).verify(
            timestamp.encode("utf-8") + body,
            bytes.fromhex(signature),
        )
    except (BadSignatureError, ValueError):
        return False
    return True


def interaction_response(database_path: str, payload: dict) -> dict:
    if payload.get("type") == 1:
        return {"type": 1}
    if payload.get("type") != 2:
        return _message("지원하지 않는 요청입니다.")

    guild_id = str(payload.get("guild_id", ""))
    if not guild_id:
        return _message("이 명령은 Discord 서버에서만 사용할 수 있습니다.")
    data = payload.get("data") or {}
    command = data.get("name", "")
    options = {option["name"]: option.get("value") for option in data.get("options", [])}
    channel_id = str(payload.get("channel_id", ""))
    member = payload.get("member") or {}
    user_id = str((member.get("user") or payload.get("user") or {}).get("id", ""))

    if command == "알림채널":
        permissions = int(member.get("permissions", "0"))
        if not (permissions & 8 or permissions & 32):
            return _message("서버 관리 권한이 필요합니다.")
        selected_channel = str(options.get("channel", ""))
        with connect(database_path) as db:
            db.execute(
                """
                INSERT INTO discord_guilds (guild_id, channel_id, configured_by)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    channel_id = excluded.channel_id,
                    configured_by = excluded.configured_by,
                    active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (guild_id, selected_channel, user_id),
            )
        return _message(f"알림 채널을 <#{selected_channel}>로 설정했습니다.")

    if command in {"구독추가", "구독삭제", "구독목록"}:
        with connect(database_path) as db:
            guild = db.execute(
                "SELECT channel_id FROM discord_guilds WHERE guild_id = ? AND active = 1",
                (guild_id,),
            ).fetchone()
        if guild is None or not guild["channel_id"]:
            return _message("먼저 `/알림채널` 명령으로 알림 채널을 설정해주세요.")
        channel_id = guild["channel_id"]

    if command == "구독추가":
        keyword = " ".join(str(options.get("keyword", "")).split())
        if not keyword or len(keyword) > 100:
            return _message("키워드는 1~100자여야 합니다.")
        with connect(database_path) as db:
            cursor = db.execute(
                """
                INSERT OR IGNORE INTO discord_subscriptions
                    (guild_id, channel_id, keyword, created_by)
                VALUES (?, ?, ?, ?)
                """,
                (guild_id, channel_id, keyword, user_id),
            )
        if cursor.rowcount == 0:
            return _message(f"`{keyword}` 키워드는 이미 구독 중입니다.")
        return _message(f"`{keyword}` 키워드를 구독했습니다.")

    if command == "구독목록":
        with connect(database_path) as db:
            rows = db.execute(
                "SELECT keyword FROM discord_subscriptions WHERE guild_id = ? ORDER BY keyword COLLATE NOCASE",
                (guild_id,),
            ).fetchall()
        if not rows:
            return _message("등록된 키워드 구독이 없습니다.")
        return _message("구독 키워드: " + ", ".join(f"`{row['keyword']}`" for row in rows))

    if command == "구독삭제":
        keyword = " ".join(str(options.get("keyword", "")).split())
        with connect(database_path) as db:
            cursor = db.execute(
                "DELETE FROM discord_subscriptions WHERE guild_id = ? AND keyword = ? COLLATE NOCASE",
                (guild_id, keyword),
            )
        return _message(
            f"`{keyword}` 구독을 삭제했습니다."
            if cursor.rowcount
            else f"`{keyword}` 구독을 찾을 수 없습니다."
        )

    if command in {"최신글", "검색"}:
        count = min(max(int(options.get("count", 5)), 1), 10)
        keyword = str(options.get("keyword", "")).strip()
        sql = """
            SELECT articles.title, articles.url, blogs.name AS blog_name
            FROM articles JOIN blogs ON blogs.id = articles.blog_id
        """
        values = []
        if command == "검색":
            sql += " WHERE articles.title LIKE ? OR articles.summary LIKE ? OR articles.content LIKE ?"
            pattern = f"%{keyword}%"
            values.extend([pattern, pattern, pattern])
        sql += " ORDER BY COALESCE(articles.published_at, articles.fetched_at) DESC, articles.id DESC LIMIT ?"
        values.append(count)
        with connect(database_path) as db:
            rows = db.execute(sql, values).fetchall()
        if not rows:
            return _message("조건에 맞는 게시글이 없습니다.")
        content = "\n".join(
            f"• **{row['title']}** · {row['blog_name']}\n  {row['url']}" for row in rows
        )
        return _message(content[:1900])

    return _message("알 수 없는 명령입니다.")


def register_commands(application_id: str, bot_token: str, guild_id: str = "") -> list:
    if guild_id:
        url = f"{DISCORD_API}/applications/{application_id}/guilds/{guild_id}/commands"
    else:
        url = f"{DISCORD_API}/applications/{application_id}/commands"
    return _discord_request(url, bot_token, method="PUT", payload=COMMANDS)


def send_channel_message(bot_token: str, channel_id: str, content: str) -> dict:
    url = f"{DISCORD_API}/channels/{channel_id}/messages"
    return _discord_request(url, bot_token, method="POST", payload={"content": content[:2000]})


def notify_new_articles(database_path: str, article_ids: list[int], bot_token: str) -> dict:
    result = {"matched": 0, "sent": 0, "failed": 0}
    if not article_ids or not bot_token:
        return result
    placeholders = ",".join("?" for _ in article_ids)
    with connect(database_path) as db:
        matches = db.execute(
            f"""
            SELECT ds.id AS subscription_id, ds.keyword, ds.channel_id,
                   a.id AS article_id, a.title, a.url, b.name AS blog_name
            FROM articles a
            JOIN blogs b ON b.id = a.blog_id
            JOIN discord_subscriptions ds
              ON instr(lower(a.title || ' ' || a.summary || ' ' || a.content),
                       lower(ds.keyword)) > 0
            JOIN discord_guilds dg
              ON dg.guild_id = ds.guild_id AND dg.active = 1
            WHERE a.id IN ({placeholders})
            ORDER BY ds.id, a.id
            """,
            article_ids,
        ).fetchall()

    for match in matches:
        with connect(database_path) as db:
            claimed = db.execute(
                """
                INSERT OR IGNORE INTO discord_deliveries
                    (subscription_id, article_id, status)
                VALUES (?, ?, 'pending')
                """,
                (match["subscription_id"], match["article_id"]),
            ).rowcount
        if not claimed:
            continue
        result["matched"] += 1
        _deliver(database_path, dict(match), bot_token, result)
    return result


def retry_failed_messages(database_path: str, bot_token: str, max_attempts: int = 3) -> dict:
    result = {"matched": 0, "sent": 0, "failed": 0}
    if not bot_token:
        return result
    with connect(database_path) as db:
        matches = db.execute(
            """
            SELECT dd.subscription_id, dd.article_id, ds.keyword, ds.channel_id,
                   a.title, a.url, b.name AS blog_name
            FROM discord_deliveries dd
            JOIN discord_subscriptions ds ON ds.id = dd.subscription_id
            JOIN discord_guilds dg ON dg.guild_id = ds.guild_id AND dg.active = 1
            JOIN articles a ON a.id = dd.article_id
            JOIN blogs b ON b.id = a.blog_id
            WHERE dd.status = 'failed' AND dd.attempts < ?
            ORDER BY dd.created_at, dd.id
            """,
            (max_attempts,),
        ).fetchall()
    for match in matches:
        result["matched"] += 1
        _deliver(database_path, dict(match), bot_token, result)
    return result


def _deliver(database_path: str, match: dict, bot_token: str, result: dict) -> None:
    content = (
        f"🔔 **{match['keyword']}** 키워드 새 글\n"
        f"**{match['title']}** · {match['blog_name']}\n{match['url']}"
    )
    try:
        send_channel_message(bot_token, match["channel_id"], content)
    except Exception as exc:
        status, error, sent_at = "failed", str(exc)[:1000], None
        result["failed"] += 1
    else:
        status, error = "sent", None
        sent_at = datetime.now(timezone.utc).isoformat()
        result["sent"] += 1
    with connect(database_path) as db:
        db.execute(
            """
            UPDATE discord_deliveries
            SET status = ?, error = ?, sent_at = ?, attempts = attempts + 1
            WHERE subscription_id = ? AND article_id = ?
            """,
            (status, error, sent_at, match["subscription_id"], match["article_id"]),
        )


def _discord_request(url: str, bot_token: str, *, method: str, payload) -> dict | list:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
            "User-Agent": "TechBlogAggregator/1.0",
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Discord API 오류 {exc.code}: {detail}") from exc
    return json.loads(body) if body else {}


def _message(content: str) -> dict:
    return {"type": 4, "data": {"content": content, "flags": EPHEMERAL}}

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .db import connect


def valid_discord_webhook_url(value: str) -> bool:
    """Only allow Discord's HTTPS webhook endpoints."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    segments = parsed.path.split("/")
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"discord.com", "discordapp.com"}
        and port in (None, 443)
        and len(segments) == 5
        and segments[:3] == ["", "api", "webhooks"]
        and segments[3].isdigit()
        and bool(segments[4])
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def send_webhook(webhook_url: str, article: dict, keyword: str) -> None:
    payload = {
        "content": f"🔔 **{keyword}** 키워드의 새 글",
        "embeds": [
            {
                "title": article["title"][:256],
                "url": article["url"],
                "description": f"{article['blog_name']} 기술 블로그",
                "color": 0x5865F2,
            }
        ],
        "allowed_mentions": {"parse": []},
    }
    request = Request(
        webhook_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "TechBlogAggregator/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        response.read()


def notify_subscription_webhooks(database_path: str, article_ids: list[int]) -> dict:
    result = {"matched": 0, "sent": 0, "failed": 0}
    if not article_ids:
        return result

    placeholders = ",".join("?" for _ in article_ids)
    with connect(database_path) as db:
        matches = db.execute(
            f"""
            SELECT s.id AS subscription_id, s.keyword, s.discord_webhook_url,
                   a.id AS article_id, a.title, a.url, b.name AS blog_name
            FROM articles a
            JOIN blogs b ON b.id = a.blog_id
            JOIN subscriptions s
              ON s.active = 1
             AND s.discord_webhook_url IS NOT NULL
             AND instr(lower(a.title || ' ' || a.summary || ' ' || a.content),
                       lower(s.keyword)) > 0
            WHERE a.id IN ({placeholders})
            ORDER BY s.id, a.id
            """,
            article_ids,
        ).fetchall()

    for row in matches:
        match = dict(row)
        with connect(database_path) as db:
            claimed = db.execute(
                """
                INSERT OR IGNORE INTO webhook_deliveries
                    (subscription_id, article_id, status)
                VALUES (?, ?, 'pending')
                """,
                (match["subscription_id"], match["article_id"]),
            ).rowcount
        if not claimed:
            continue

        result["matched"] += 1
        _deliver(database_path, match, result)
    return result


def retry_failed_webhooks(database_path: str, max_attempts: int = 3) -> dict:
    result = {"matched": 0, "sent": 0, "failed": 0}
    with connect(database_path) as db:
        rows = db.execute(
            """
            SELECT wd.subscription_id, wd.article_id, s.keyword,
                   s.discord_webhook_url, a.title, a.url, b.name AS blog_name
            FROM webhook_deliveries wd
            JOIN subscriptions s ON s.id = wd.subscription_id
            JOIN articles a ON a.id = wd.article_id
            JOIN blogs b ON b.id = a.blog_id
            WHERE wd.status = 'failed' AND wd.attempts < ?
              AND s.active = 1 AND s.discord_webhook_url IS NOT NULL
            ORDER BY wd.created_at, wd.id
            """,
            (max_attempts,),
        ).fetchall()
    for row in rows:
        result["matched"] += 1
        _deliver(database_path, dict(row), result)
    return result


def _deliver(database_path: str, match: dict, result: dict) -> None:
    try:
        send_webhook(match["discord_webhook_url"], match, match["keyword"])
    except Exception as exc:
        error = f"HTTP {exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__
        status, sent_at = "failed", None
        result["failed"] += 1
    else:
        status, error = "sent", None
        sent_at = datetime.now(timezone.utc).isoformat()
        result["sent"] += 1
    with connect(database_path) as db:
        db.execute(
            """
            UPDATE webhook_deliveries
            SET status = ?, error = ?, sent_at = ?, attempts = attempts + 1
            WHERE subscription_id = ? AND article_id = ?
            """,
            (status, error, sent_at, match["subscription_id"], match["article_id"]),
        )

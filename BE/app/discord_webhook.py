from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .db import connect


def valid_discord_webhook_url(value: str) -> bool:
    """Only allow Discord's HTTPS webhook endpoints."""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"discord.com", "discordapp.com"}
        and parsed.path.startswith("/api/webhooks/")
        and parsed.username is None
        and parsed.password is None
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
        try:
            send_webhook(match["discord_webhook_url"], match, match["keyword"])
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
                UPDATE webhook_deliveries SET status = ?, error = ?, sent_at = ?
                WHERE subscription_id = ? AND article_id = ?
                """,
                (status, error, sent_at, match["subscription_id"], match["article_id"]),
            )
    return result

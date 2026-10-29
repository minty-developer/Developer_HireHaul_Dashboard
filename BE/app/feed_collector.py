from __future__ import annotations

from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .db import (
    connect,
    get_active_blogs,
    get_blog,
    update_blog_sync_status,
    upsert_articles,
)
from .discord_bot import notify_new_articles
from .discord_webhook import notify_subscription_webhooks, retry_failed_webhooks
from .feed_parser import FeedParseError, parse_feed


USER_AGENT = "TechBlogAggregator/1.0"


class CollectionError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_blog(
    database_path: str,
    blog_id: int,
    timeout: int = 20,
    discord_bot_token: str = "",
) -> dict:
    blog = get_blog(database_path, blog_id)
    if blog is None:
        raise LookupError("블로그를 찾을 수 없습니다.")
    if not blog["active"]:
        raise CollectionError("비활성화된 블로그는 수집할 수 없습니다.")

    checked_at = _now()
    headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"}
    if blog["etag"]:
        headers["If-None-Match"] = blog["etag"]
    if blog["last_modified"]:
        headers["If-Modified-Since"] = blog["last_modified"]

    request = Request(blog["feed_url"], headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read()
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")

        articles = parse_feed(data, blog_id, fetched_at=checked_at)
        entry_keys = list({article["entry_key"] for article in articles})
        existing_keys = set()
        if entry_keys:
            placeholders = ",".join("?" for _ in entry_keys)
            with connect(database_path) as db:
                existing_keys = {
                    row["entry_key"]
                    for row in db.execute(
                        f"SELECT entry_key FROM articles WHERE blog_id = ? AND entry_key IN ({placeholders})",
                        [blog_id, *entry_keys],
                    ).fetchall()
                }
        saved = upsert_articles(database_path, articles)
        new_keys = [key for key in entry_keys if key not in existing_keys]
        new_article_ids = []
        if new_keys:
            placeholders = ",".join("?" for _ in new_keys)
            with connect(database_path) as db:
                new_article_ids = [
                    row["id"]
                    for row in db.execute(
                        f"SELECT id FROM articles WHERE blog_id = ? AND entry_key IN ({placeholders})",
                        [blog_id, *new_keys],
                    ).fetchall()
                ]
        notifications = notify_new_articles(
            database_path, new_article_ids, discord_bot_token
        )
        webhook_notifications = notify_subscription_webhooks(
            database_path, new_article_ids
        )
        update_blog_sync_status(
            database_path,
            blog_id,
            checked_at=checked_at,
            succeeded=True,
            etag=etag,
            last_modified=last_modified,
        )
        return {
            "blog_id": blog_id,
            "blog": blog["name"],
            "status": "updated",
            "saved": saved,
            "new": len(new_article_ids),
            "notifications": notifications,
            "webhook_notifications": webhook_notifications,
        }
    except HTTPError as exc:
        if exc.code == 304:
            update_blog_sync_status(
                database_path,
                blog_id,
                checked_at=checked_at,
                succeeded=True,
            )
            return {
                "blog_id": blog_id,
                "blog": blog["name"],
                "status": "not_modified",
                "saved": 0,
            }
        _record_failure(database_path, blog_id, checked_at, f"HTTP {exc.code}")
        raise CollectionError(f"RSS 요청 실패: HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError, FeedParseError) as exc:
        message = str(exc)
        _record_failure(database_path, blog_id, checked_at, message)
        raise CollectionError(f"RSS 수집 실패: {message}") from exc


def _record_failure(database_path: str, blog_id: int, checked_at: str, error: str) -> None:
    update_blog_sync_status(
        database_path,
        blog_id,
        checked_at=checked_at,
        succeeded=False,
        error=error[:1000],
    )


def collect_all(
    database_path: str, timeout: int = 20, discord_bot_token: str = ""
) -> dict:
    results = []
    failed = 0
    saved = 0

    for blog in get_active_blogs(database_path):
        try:
            result = collect_blog(
                database_path,
                blog["id"],
                timeout=timeout,
                discord_bot_token=discord_bot_token,
            )
            saved += result["saved"]
        except CollectionError as exc:
            failed += 1
            result = {
                "blog_id": blog["id"],
                "blog": blog["name"],
                "status": "failed",
                "saved": 0,
                "error": str(exc),
            }
        results.append(result)

    webhook_retries = retry_failed_webhooks(database_path)
    return {
        "total": len(results),
        "succeeded": len(results) - failed,
        "failed": failed,
        "saved": saved,
        "webhook_retries": webhook_retries,
        "results": results,
    }

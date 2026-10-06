from __future__ import annotations

import calendar
from datetime import datetime, timezone
from time import struct_time

import feedparser


class FeedParseError(ValueError):
    pass


def _iso_datetime(value: struct_time | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(
        calendar.timegm(value),
        tz=timezone.utc,
    ).isoformat()


def _content(entry: dict) -> str:
    content = entry.get("content") or []
    if content:
        return content[0].get("value", "")
    return entry.get("summary", "")


def parse_feed(
    data: bytes | str,
    blog_id: int,
    fetched_at: str | None = None,
) -> list[dict]:
    """RSS/Atom 문서를 DB에 저장할 공통 게시글 형식으로 변환한다."""
    parsed = feedparser.parse(data)
    if parsed.bozo and not parsed.entries:
        raise FeedParseError(f"피드를 파싱할 수 없습니다: {parsed.bozo_exception}")

    collected_at = fetched_at or datetime.now(timezone.utc).isoformat()
    articles = []

    for entry in parsed.entries:
        title = entry.get("title", "").strip()
        url = entry.get("link", "").strip()
        entry_key = (entry.get("id") or entry.get("guid") or url).strip()
        if not title or not url or not entry_key:
            continue

        published = (
            entry["published_parsed"]
            if "published_parsed" in entry
            else entry.get("created_parsed")
        )
        updated = entry["updated_parsed"] if "updated_parsed" in entry else None
        articles.append({
            "blog_id": blog_id,
            "entry_key": entry_key,
            "title": title,
            "url": url,
            "author": entry.get("author", "").strip(),
            "summary": entry.get("summary", ""),
            "content": _content(entry),
            "published_at": _iso_datetime(published),
            "feed_updated_at": _iso_datetime(updated),
            "fetched_at": collected_at,
        })

    return articles

"""RSS 수집기(3번 담당, rss-collector/)가 만든 JSON을 DB에 넣는다.

- blogs.json: [{"name", "rss_url", "category"?, "enabled"?, "company"?, "site_url"?}]
- posts.json: [{"title", "link", "published", "blog", "summary"?, "content"?, "author"?}]

글은 `link`를 entry_key로 써서 (blog_id, entry_key)로 중복을 막는다. 같은 파일을
여러 번 가져와도 글이 두 번 저장되지 않는다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

from .db import connect, upsert_blog


class RssImportError(ValueError):
    """가져올 JSON 형식이 잘못됐을 때."""


def load_json_list(path: str | Path) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise RssImportError(f"{path}를 읽을 수 없습니다: {error}") from None
    if not isinstance(data, list):
        raise RssImportError(f"{path}는 JSON 배열이어야 합니다.")
    return [item for item in data if isinstance(item, dict)]


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def normalize_date(value) -> str | None:
    """ISO 8601(`...Z` 포함)이나 RSS의 RFC 2822(`Wed, 30 Sep 2026 12:00:11 GMT`) 날짜를
    `2026-09-30T12:00:11+00:00` 형식의 UTC 문자열로 바꾼다. 목록 정렬과 기간 검색이
    이 문자열을 그대로 비교하므로 형식을 하나로 맞춘다. 읽을 수 없으면 None."""
    text = _text(value)
    if not text:
        return None
    try:
        date = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            date = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc).isoformat(timespec="seconds")


def _site_url(feed_url: str) -> str:
    parts = urlsplit(feed_url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else feed_url


def import_blogs(database_path: str, blogs: list[dict]) -> dict[str, int]:
    """블로그를 feed_url 기준으로 등록·갱신하고 {블로그 이름: id}를 돌려준다."""
    ids: dict[str, int] = {}
    for blog in blogs:
        name = _text(blog.get("name"))
        feed_url = _text(blog.get("rss_url"))
        if not name or not feed_url:
            continue
        ids[name] = upsert_blog(database_path, {
            "name": name,
            # 회사명이 없으면 3번이 추가하기 전까지 블로그 이름을 쓴다.
            "company": _text(blog.get("company")) or name,
            "feed_url": feed_url,
            "site_url": _text(blog.get("site_url")) or _site_url(feed_url),
            "active": 1 if blog.get("enabled", True) else 0,
        })
    return ids


def import_posts(database_path: str, posts: list[dict], blog_ids: dict[str, int]) -> dict:
    """글을 저장한다. 이미 있는 글은 제목·날짜를 갱신하고, 요약·본문·작성자는 새 값이 있을 때만 바꾼다."""
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows, unknown_blogs, invalid = [], set(), 0
    for post in posts:
        title, link, blog = _text(post.get("title")), _text(post.get("link")), _text(post.get("blog"))
        if not title or not link:
            invalid += 1
            continue
        if blog not in blog_ids:
            unknown_blogs.add(blog or "(이름 없음)")
            continue
        rows.append({
            "blog_id": blog_ids[blog],
            "entry_key": link,
            "title": title,
            "url": link,
            "author": _text(post.get("author")),
            "summary": _text(post.get("summary")),
            "content": _text(post.get("content")),
            "published_at": normalize_date(post.get("published")),
            "fetched_at": fetched_at,
        })

    with connect(database_path) as db:
        before = db.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        db.executemany(
            """
            INSERT INTO articles (
                blog_id, entry_key, title, url, author, summary, content,
                published_at, fetched_at
            ) VALUES (
                :blog_id, :entry_key, :title, :url, :author, :summary, :content,
                :published_at, :fetched_at
            )
            ON CONFLICT(blog_id, entry_key) DO UPDATE SET
                title = excluded.title,
                published_at = COALESCE(excluded.published_at, articles.published_at),
                author = COALESCE(NULLIF(excluded.author, ''), articles.author),
                summary = COALESCE(NULLIF(excluded.summary, ''), articles.summary),
                content = COALESCE(NULLIF(excluded.content, ''), articles.content),
                updated_at = CURRENT_TIMESTAMP
            """,
            rows,
        )
        after = db.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        # 화면에 '최근 수집 성공 시각'이 보이도록 가져온 블로그의 수집 상태를 갱신한다.
        imported_blog_ids = sorted({row["blog_id"] for row in rows})
        db.executemany(
            "UPDATE blogs SET last_checked_at = ?, last_success_at = ?, last_error = NULL WHERE id = ?",
            [(fetched_at, fetched_at, blog_id) for blog_id in imported_blog_ids],
        )

    return {
        "new": after - before,
        "existing": len(rows) - (after - before),
        "invalid": invalid,
        "unknown_blogs": sorted(unknown_blogs),
    }


def import_rss_files(database_path: str, blogs_path: str | Path, posts_path: str | Path) -> dict:
    blog_ids = import_blogs(database_path, load_json_list(blogs_path))
    result = import_posts(database_path, load_json_list(posts_path), blog_ids)
    return {"blogs": len(blog_ids), **result}

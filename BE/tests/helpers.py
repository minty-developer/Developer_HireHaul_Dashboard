"""테스트용 데이터 준비 함수.

실제 게시글 저장(수집·중복 처리)은 RSS 담당 코드의 몫이라, 테스트에서는
articles 테이블에 바로 INSERT 한다.
"""
from __future__ import annotations

from app.db import connect

ARTICLE_DEFAULTS = {
    "author": "",
    "summary": "",
    "content": "",
    "published_at": None,
    "feed_updated_at": None,
}


def insert_articles(database_path: str, articles: list[dict]) -> None:
    rows = [{**ARTICLE_DEFAULTS, **article} for article in articles]
    with connect(database_path) as db:
        db.executemany(
            """
            INSERT INTO articles (
                blog_id, entry_key, title, url, author, summary, content,
                published_at, feed_updated_at, fetched_at
            ) VALUES (
                :blog_id, :entry_key, :title, :url, :author, :summary, :content,
                :published_at, :feed_updated_at, :fetched_at
            )
            """,
            rows,
        )

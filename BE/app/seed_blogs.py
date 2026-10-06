from __future__ import annotations

from .db import upsert_blog


DEFAULT_BLOGS = (
    {
        "name": "Kakao Tech",
        "company": "카카오",
        "feed_url": "https://tech.kakao.com/feed/",
        "site_url": "https://tech.kakao.com/",
        "description": "카카오 기술 블로그",
    },
    {
        "name": "NAVER D2",
        "company": "네이버",
        "feed_url": "https://d2.naver.com/d2.atom",
        "site_url": "https://d2.naver.com/",
        "description": "네이버 개발자 기술 플랫폼",
    },
    {
        "name": "LY Corporation Tech Blog",
        "company": "LY Corporation",
        "feed_url": "https://techblog.lycorp.co.jp/ko/feed/index.xml",
        "site_url": "https://techblog.lycorp.co.jp/ko/blog",
        "description": "LY Corporation 한국어 기술 블로그",
    },
)


def seed_default_blogs(database_path: str) -> int:
    for blog in DEFAULT_BLOGS:
        upsert_blog(database_path, blog)
    return len(DEFAULT_BLOGS)

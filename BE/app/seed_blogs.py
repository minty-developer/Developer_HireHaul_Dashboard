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
    {
        "name": "토스 테크",
        "company": "토스",
        "feed_url": "https://toss.tech/rss.xml",
        "site_url": "https://toss.tech/",
        "description": "토스 기술 블로그",
    },
    {
        "name": "우아한형제들 기술블로그",
        "company": "우아한형제들",
        "feed_url": "https://techblog.woowahan.com/feed/",
        "site_url": "https://techblog.woowahan.com/",
        "description": "배달의민족 운영사 우아한형제들 기술 블로그",
    },
    {
        "name": "당근 테크 블로그",
        "company": "당근",
        "feed_url": "https://medium.com/feed/daangn",
        "site_url": "https://medium.com/daangn",
        "description": "당근 기술 블로그",
    },
    {
        "name": "뱅크샐러드 기술 블로그",
        "company": "뱅크샐러드",
        "feed_url": "https://blog.banksalad.com/rss.xml",
        "site_url": "https://blog.banksalad.com/",
        "description": "뱅크샐러드 기술 블로그",
    },
    {
        "name": "무신사 테크 블로그",
        "company": "무신사",
        "feed_url": "https://medium.com/feed/musinsa-tech",
        "site_url": "https://techblog.musinsa.com/",
        "description": "무신사 기술 블로그",
    },
    {
        "name": "여기어때 기술블로그",
        "company": "여기어때",
        "feed_url": "https://techblog.gccompany.co.kr/feed",
        "site_url": "https://techblog.gccompany.co.kr/",
        "description": "여기어때컴퍼니 기술 블로그",
    },
    {
        "name": "Hyperconnect Tech Blog",
        "company": "하이퍼커넥트",
        "feed_url": "https://hyperconnect.github.io/feed.xml",
        "site_url": "https://hyperconnect.github.io/",
        "description": "하이퍼커넥트 기술 블로그",
    },
    {
        "name": "데브시스터즈 기술 블로그",
        "company": "데브시스터즈",
        "feed_url": "https://tech.devsisters.com/rss.xml",
        "site_url": "https://tech.devsisters.com/",
        "description": "데브시스터즈 기술 블로그",
    },
    {
        "name": "NHN Cloud Meetup",
        "company": "NHN",
        "feed_url": "https://meetup.nhncloud.com/rss",
        "site_url": "https://meetup.nhncloud.com/",
        "description": "NHN 기술 블로그",
    },
    {
        "name": "카카오뱅크 기술블로그",
        "company": "카카오뱅크",
        "feed_url": "https://tech.kakaobank.com/index.xml",
        "site_url": "https://tech.kakaobank.com/",
        "description": "카카오뱅크 기술 블로그",
    },
    {
        "name": "WATCHA 기술 블로그",
        "company": "왓챠",
        "feed_url": "https://medium.com/feed/watcha",
        "site_url": "https://medium.com/watcha",
        "description": "왓챠 기술 블로그",
    },
    {
        "name": "요기요 기술블로그",
        "company": "요기요",
        "feed_url": "https://techblog.yogiyo.co.kr/feed",
        "site_url": "https://techblog.yogiyo.co.kr/",
        "description": "요기요 기술 블로그",
    },
    {
        "name": "네이버 플레이스 개발 블로그",
        "company": "네이버",
        "feed_url": "https://medium.com/feed/naver-place-dev",
        "site_url": "https://medium.com/naver-place-dev",
        "description": "네이버 플레이스 개발 블로그",
    },
)


def seed_default_blogs(database_path: str) -> int:
    for blog in DEFAULT_BLOGS:
        upsert_blog(database_path, blog)
    return len(DEFAULT_BLOGS)

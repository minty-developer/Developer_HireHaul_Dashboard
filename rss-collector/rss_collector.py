
import json
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

import feedparser
import requests
from bs4 import BeautifulSoup


# ==========================================
# 1. RSS 출처 목록 불러오기
# ==========================================

BLOGS_FILE = Path(__file__).parent / "blogs.json"


def load_blogs():
    with open(BLOGS_FILE, "r", encoding="utf-8-sig") as file:
        blogs = json.load(file)

    return [
        blog for blog in blogs
        if blog.get("enabled", True)
    ]


BLOGS = load_blogs()


# ==========================================
# 2. RSS 피드 가져오기
# ==========================================

def fetch_feed(rss_url):
    request = Request(
        rss_url,
        headers={"User-Agent": "TechBlogAggregator/1.0"}
    )

    with urlopen(request, timeout=15) as response:
        return feedparser.parse(response.read())


# ==========================================
# 3. Google 게시글 원문에서 발행일 가져오기
# ==========================================

def fetch_google_published_date(url):

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        scripts = soup.find_all(
            "script",
            type="application/ld+json"
        )

        def find_date(data):

            if isinstance(data, list):

                for item in data:
                    result = find_date(item)

                    if result:
                        return result

            elif isinstance(data, dict):

                if data.get("datePublished"):
                    return data["datePublished"]

                for value in data.values():
                    result = find_date(value)

                    if result:
                        return result

            return None

        for script in scripts:

            script_text = script.string or script.get_text()

            if not script_text:
                continue

            try:
                data = json.loads(script_text)

                published = find_date(data)

                if published:
                    return str(published).strip()

            except (json.JSONDecodeError, TypeError):
                continue

    except requests.RequestException as error:
        print(f"Google 원문 날짜 확인 실패: {error}")

    return None


# ==========================================
# 4. 날짜 문자열 변환
# ==========================================

def convert_date(value):

    if not value:
        return None

    try:
        date = parsedate_to_datetime(value)

        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)

        return date.astimezone(timezone.utc).isoformat(
            timespec="seconds"
        )

    except (TypeError, ValueError, OverflowError):

        try:
            date = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)

            return date.astimezone(timezone.utc).isoformat(
                timespec="seconds"
            )

        except (TypeError, ValueError, OverflowError):
            return None


# ==========================================
# 5. 게시글 날짜 정규화
# ==========================================

def normalize_date(entry):

    # 1. RSS 날짜 필드 확인
    for field in ("published_parsed", "updated_parsed"):

        parsed = entry.get(field)

        if parsed:

            try:
                date = datetime(
                    *parsed[:6],
                    tzinfo=timezone.utc
                )

                return date.isoformat(timespec="seconds")

            except (TypeError, ValueError, OverflowError):
                continue

    # 2. RSS 날짜 문자열 확인
    for field in ("published", "updated", "created"):

        value = entry.get(field)

        if value:
            date = convert_date(value)

            if date:
                return date

    # 3. Google Developers Blog 원문 날짜 확인
    if entry.get("_blog_name") == "Google Developers Blog":

        link = entry.get("link")

        if link:
            value = fetch_google_published_date(link)

            if value:
                date = convert_date(value)

                if date:
                    return date

    # 4. 날짜를 확인할 수 없으면 None
    return None


# ==========================================
# 6. 게시글 데이터 정규화
# ==========================================

def clean_text(value):
    """RSS 요약의 HTML 태그를 지우고 공백을 하나로 정리한다."""

    if not isinstance(value, str) or not value.strip():
        return ""

    text = BeautifulSoup(value, "html.parser").get_text(" ")

    # 눈에 안 보이는 폭 없는 공백(U+200B)도 지운다.
    text = text.replace("​", " ")

    return " ".join(text.split())


def normalize_post(entry, blog_name):

    title = entry.get("title", "")
    link = entry.get("link", "")

    if not isinstance(title, str) or not isinstance(link, str):
        return None

    title = title.strip()
    link = link.strip()

    if not title or not link:
        return None

    entry_with_blog = dict(entry)
    entry_with_blog["_blog_name"] = blog_name

    return {
        "title": title,
        "link": link,
        "published": normalize_date(entry_with_blog),
        "blog": blog_name,
        # 검색과 글 상세 화면에 쓰인다 (RSS 2.0의 description도 feedparser가 summary로 넘겨줌).
        "summary": clean_text(entry.get("summary")),
        "author": clean_text(entry.get("author")),
    }


# ==========================================
# 7. 게시글 최신순 정렬
# ==========================================

def sort_posts(posts):

    def sort_key(post):

        value = post.get("published")

        if not value:
            return datetime.min.replace(tzinfo=timezone.utc)

        try:
            date = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)

            return date.astimezone(timezone.utc)

        except (TypeError, ValueError, OverflowError):
            return datetime.min.replace(tzinfo=timezone.utc)

    return sorted(posts, key=sort_key, reverse=True)


# ==========================================
# 8. RSS 게시글 수집
# ==========================================

def collect_posts(seen_links=None):

    if seen_links is None:
        seen_links = set()
    else:
        seen_links = set(seen_links)

    collected_posts = []

    for blog in BLOGS:

        name = blog["name"]

        print(f"\n[{name}] 수집 시작")

        try:
            feed = fetch_feed(blog["rss_url"])

            if feed.bozo:
                print(
                    f"[{name}] RSS 형식 또는 읽기 경고가 발생했습니다."
                )

            if not feed.entries:
                print(
                    f"[{name}] 게시글이 없거나 RSS를 읽지 못했습니다."
                )
                continue

            blog_count = 0

            for entry in feed.entries:

                post = normalize_post(entry, name)

                if post is None:
                    continue

                if post["link"] in seen_links:
                    continue

                seen_links.add(post["link"])
                collected_posts.append(post)
                blog_count += 1

            print(f"[{name}] 새 게시글 {blog_count}개 수집")

        except Exception as error:

            print(f"[{name}] 수집 실패: {error}")

    return sort_posts(collected_posts)

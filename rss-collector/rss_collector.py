
import feedparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen


BLOGS = [
    {
        "name": "NAVER D2",
        "rss_url": "https://d2.naver.com/d2.atom",
    },
    {
        "name": "Python Blog",
        "rss_url": "https://blog.python.org/feeds/posts/default",
    },
]


def fetch_feed(rss_url):
    """RSS 주소에서 데이터를 가져온다."""
    request = Request(
        rss_url,
        headers={"User-Agent": "TechBlogAggregator/1.0"},
    )

    with urlopen(request, timeout=15) as response:
        return feedparser.parse(response.read())


def normalize_date(entry):
    """작성일을 ISO 8601 형식으로 통일한다."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)

        if parsed:
            date = datetime(
                *parsed[:6],
                tzinfo=timezone.utc,
            )
            return date.isoformat(timespec="seconds")

    for field in ("published", "updated", "created"):
        value = entry.get(field)

        if not value:
            continue

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
                continue

    return None


def normalize_post(entry, blog_name):
    """게시글 데이터를 필요한 형식으로 정리한다."""
    title = entry.get("title", "")
    link = entry.get("link", "")

    if not isinstance(title, str) or not isinstance(link, str):
        return None

    title = title.strip()
    link = link.strip()

    if not title or not link:
        return None

    return {
        "title": title,
        "link": link,
        "published": normalize_date(entry),
        "blog": blog_name,
    }


def sort_posts(posts):
    """작성일이 최신인 게시글부터 정렬한다. 날짜가 없으면 마지막에 둔다."""
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


def collect_posts(seen_links=None):
    """등록된 블로그에서 새로운 게시글만 수집한다."""
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
                print(f"[{name}] RSS 형식 또는 읽기 경고가 발생했습니다.")

            if not feed.entries:
                print(f"[{name}] 게시글이 없거나 RSS를 읽지 못했습니다.")
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

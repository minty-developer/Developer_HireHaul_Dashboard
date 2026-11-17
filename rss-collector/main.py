
import json
from pathlib import Path

from rss_collector import collect_posts, sort_posts


BASE_DIR = Path(__file__).resolve().parent
FILE_NAME = BASE_DIR / "posts.json"


def load_posts():
    """기존 JSON 데이터를 불러온다."""
    if not FILE_NAME.exists():
        return []

    try:
        with FILE_NAME.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            print("저장 데이터가 리스트 형식이 아닙니다.")
            return []

        return [
            post for post in data
            if isinstance(post, dict)
        ]

    except (json.JSONDecodeError, OSError) as error:
        print(f"기존 데이터 불러오기 실패: {error}")
        raise


def save_posts(posts):
    """정리된 게시글을 JSON 파일에 저장한다."""
    temp_file = FILE_NAME.with_suffix(".tmp")

    try:
        with temp_file.open("w", encoding="utf-8") as file:
            json.dump(
                posts,
                file,
                ensure_ascii=False,
                indent=4,
            )

        temp_file.replace(FILE_NAME)

    except OSError:
        if temp_file.exists():
            temp_file.unlink()
        raise


def main():
    posts = load_posts()

    seen_links = {
        post["link"].strip()
        for post in posts
        if isinstance(post.get("link"), str)
        and post["link"].strip()
    }

    print("기존 게시글:", len(posts), "개")

    new_posts = collect_posts(seen_links)
    posts.extend(new_posts)

    posts = sort_posts(posts)
    save_posts(posts)

    print("\n========== 수집 결과 ==========")
    print("새 게시글:", len(new_posts), "개")
    print("전체 게시글:", len(posts), "개")
    print("저장 위치:", FILE_NAME)
    print("================================")

    if posts:
        print("\n최신 게시글 5개")

        for post in posts[:5]:
            print("-", post.get("title", "제목 없음"))
            print(" ", post.get("published") or "작성일 없음")
            print(" ", post.get("link", ""))


if __name__ == "__main__":
    main()

import json
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner
from fastapi.testclient import TestClient

from app import create_app
from app.cli import cli
from app.db import connect
from app.rss_import import normalize_date

BLOGS = [
    {"name": "NAVER D2", "rss_url": "https://d2.naver.com/d2.atom", "category": "개발 전반", "enabled": True},
    {"name": "React Blog", "rss_url": "https://react.dev/rss.xml", "category": "Frontend", "enabled": True},
    {"name": "OpenAI News", "rss_url": "https://openai.com/news/rss.xml", "category": "AI", "enabled": False},
]
POSTS = [
    {"title": "컨테이너처럼 쓰고, VM처럼 격리하기", "link": "https://d2.naver.com/helloworld/1",
     "published": "2026-11-11T08:21:15+00:00", "blog": "NAVER D2"},
    {"title": "React Compiler 소개", "link": "https://react.dev/blog/compiler",
     "published": "2026-11-10T00:00:00+00:00", "blog": "React Blog"},
    {"title": "출처 모르는 글", "link": "https://example.com/x", "published": None, "blog": "Unknown Blog"},
    {"title": "", "link": "https://example.com/no-title", "blog": "NAVER D2"},
]


class RssImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.app = create_app({
            "TESTING": True,
            "APP_ENV": "testing",
            "DATABASE_PATH": str(self.dir / "test.db"),
        })
        self.database_path = self.app.state.config["DATABASE_PATH"]
        self.blogs_path = self.write("blogs.json", BLOGS, bom=True)  # 3번 파일은 BOM이 붙어 있다.
        self.posts_path = self.write("posts.json", POSTS)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data, bom=False):
        path = self.dir / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8-sig" if bom else "utf-8")
        return str(path)

    def run_import(self, *paths):
        return CliRunner().invoke(
            cli, ["import-rss", *(paths or (self.blogs_path, self.posts_path))],
            obj=self.app.state.config,
        )

    def test_imports_blogs_and_posts_and_reports_skips(self):
        result = self.run_import()

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("블로그 3개, 새 글 2개, 이미 있던 글 0개", result.output)
        self.assertIn("건너뛴 글: 1개", result.output)
        self.assertIn("Unknown Blog", result.output)
        with connect(self.database_path) as db:
            blogs = {row["name"]: dict(row) for row in db.execute("SELECT * FROM blogs")}
            article = db.execute(
                "SELECT * FROM articles WHERE entry_key = 'https://react.dev/blog/compiler'"
            ).fetchone()
        self.assertEqual(blogs["React Blog"]["company"], "React Blog")
        self.assertEqual(blogs["React Blog"]["site_url"], "https://react.dev")
        self.assertEqual(blogs["OpenAI News"]["active"], 0)
        self.assertIsNotNone(blogs["NAVER D2"]["last_success_at"])
        self.assertEqual(article["url"], "https://react.dev/blog/compiler")
        self.assertEqual(article["published_at"], "2026-11-10T00:00:00+00:00")

    def test_running_twice_does_not_duplicate_and_fills_new_summary(self):
        self.run_import()
        posts = [{**POSTS[0], "summary": "Kata Containers 도입기", "title": "제목 수정됨"}]
        result = self.run_import(self.blogs_path, self.write("posts2.json", posts))

        self.assertIn("새 글 0개, 이미 있던 글 1개", result.output)
        with connect(self.database_path) as db:
            count = db.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            row = db.execute("SELECT title, summary FROM articles WHERE entry_key = ?",
                             (POSTS[0]["link"],)).fetchone()
        self.assertEqual(count, 2)
        self.assertEqual((row["title"], row["summary"]), ("제목 수정됨", "Kata Containers 도입기"))

    def test_imported_posts_are_searchable_through_api(self):
        self.run_import()
        client = TestClient(self.app)

        found = client.get("/api/articles?q=컨테이너").json()
        blogs = client.get("/api/blogs").json()

        self.assertEqual([a["title"] for a in found["articles"]], ["컨테이너처럼 쓰고, VM처럼 격리하기"])
        self.assertEqual(found["articles"][0]["blog_name"], "NAVER D2")
        self.assertEqual(blogs["count"], 2)  # 꺼진 블로그(OpenAI News)는 목록에서 빠진다.

    def test_dates_are_normalized_to_utc_iso(self):
        for raw, expected in [
            ("Wed, 30 Sep 2026 12:00:11 GMT", "2026-09-30T12:00:11+00:00"),
            ("2026-11-12T00:00:00Z", "2026-11-12T00:00:00+00:00"),
            ("2026-11-11T17:00:00+09:00", "2026-11-11T08:00:00+00:00"),
            ("2026-11-11", "2026-11-11T00:00:00+00:00"),
            ("날짜 아님", None),
            (None, None),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_date(raw), expected)

    def test_rss_dates_sort_with_iso_dates(self):
        posts = [
            {"title": "옛날 글", "link": "https://e.com/old", "blog": "NAVER D2",
             "published": "Wed, 30 Sep 2026 12:00:11 GMT"},
            {"title": "새 글", "link": "https://e.com/new", "blog": "NAVER D2",
             "published": "2026-11-12T00:00:00Z"},
        ]
        self.run_import(self.blogs_path, self.write("mixed.json", posts))

        titles = [a["title"] for a in TestClient(self.app).get("/api/articles").json()["articles"]]
        self.assertEqual(titles, ["새 글", "옛날 글"])

    def test_rejects_non_list_json(self):
        result = self.run_import(self.write("bad.json", {"posts": []}), self.posts_path)

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("JSON 배열이어야 합니다", result.output)


if __name__ == "__main__":
    unittest.main()

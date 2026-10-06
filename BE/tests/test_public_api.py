import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import upsert_articles, upsert_blog


class PublicApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp.name) / "test.db")
        self.app = create_app({
            "TESTING": True,
            "APP_ENV": "testing",
            "DATABASE_PATH": self.database_path,
            "ADMIN_API_KEY": "test-admin-key",
            "CORS_ORIGINS": "http://localhost:3000",
        })
        self.client = self.app.test_client()
        self.blog_id = upsert_blog(self.database_path, {
            "name": "Example Tech",
            "company": "Example",
            "feed_url": "https://example.com/feed.xml",
            "site_url": "https://example.com/tech",
        })
        upsert_articles(self.database_path, [
            {
                "blog_id": self.blog_id,
                "entry_key": "python-article",
                "title": "Python API 설계",
                "url": "https://example.com/python",
                "author": "Backend Team",
                "summary": "Flask API 설계 방법",
                "content": "REST API와 테스트",
                "published_at": "2026-10-05T01:00:00+00:00",
                "fetched_at": "2026-10-06T01:00:00+00:00",
            },
            {
                "blog_id": self.blog_id,
                "entry_key": "frontend-article",
                "title": "React 렌더링 최적화",
                "url": "https://example.com/react",
                "summary": "프론트엔드 성능 개선",
                "published_at": "2026-09-20T01:00:00+00:00",
                "fetched_at": "2026-10-06T01:00:00+00:00",
            },
        ])

    def tearDown(self):
        self.temp.cleanup()

    def test_lists_articles_without_content(self):
        response = self.client.get("/api/articles?limit=1&offset=0")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["count"], 1)
        self.assertEqual(response.json["total"], 2)
        self.assertNotIn("content", response.json["articles"][0])

    def test_searches_and_filters_articles(self):
        response = self.client.get(
            f"/api/articles?q=Flask&blog_id={self.blog_id}&from=2026-10-01&to=2026-10-06"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["total"], 1)
        self.assertEqual(response.json["articles"][0]["title"], "Python API 설계")

    def test_returns_article_detail(self):
        article_id = self.client.get("/api/articles?q=Python").json["articles"][0]["id"]
        response = self.client.get(f"/api/articles/{article_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["article"]["content"], "REST API와 테스트")

    def test_validates_article_query(self):
        queries = (
            "limit=0",
            "limit=101",
            "offset=-1",
            "blog_id=invalid",
            "blog_id=0",
            "from=2026-99-01",
            "from=2026-10-07&to=2026-10-06",
        )
        for query in queries:
            with self.subTest(query=query):
                response = self.client.get(f"/api/articles?{query}")
                self.assertEqual(response.status_code, 400)

    def test_returns_404_for_unknown_article(self):
        response = self.client.get("/api/articles/9999")
        self.assertEqual(response.status_code, 404)

    def test_lists_and_gets_blogs_with_article_count(self):
        response = self.client.get("/api/blogs")
        detail = self.client.get(f"/api/blogs/{self.blog_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["blogs"][0]["article_count"], 2)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json["blog"]["name"], "Example Tech")

    def test_returns_404_for_unknown_blog(self):
        response = self.client.get("/api/blogs/9999")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()

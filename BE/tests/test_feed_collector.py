import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from app import create_app
from app.db import connect, get_blog, upsert_blog
from app.feed_collector import CollectionError, collect_blog


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test</title><item>
<guid>article-1</guid><title>Collected article</title>
<link>https://example.com/article-1</link>
</item></channel></rss>"""


class FakeResponse:
    def __init__(self, body=RSS, headers=None):
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body


class FeedCollectorTest(unittest.TestCase):
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
            "name": "Test Blog",
            "company": "Test Company",
            "feed_url": "https://example.com/feed.xml",
            "site_url": "https://example.com/tech",
        })

    def tearDown(self):
        self.temp.cleanup()

    @patch("app.feed_collector.urlopen")
    def test_collects_and_saves_feed(self, urlopen):
        urlopen.return_value = FakeResponse(headers={
            "ETag": '"feed-v1"',
            "Last-Modified": "Tue, 06 Oct 2026 01:00:00 GMT",
        })

        result = collect_blog(self.database_path, self.blog_id)

        self.assertEqual(result["saved"], 1)
        with connect(self.database_path) as db:
            article = db.execute("SELECT * FROM articles").fetchone()
        blog = get_blog(self.database_path, self.blog_id)
        self.assertEqual(article["title"], "Collected article")
        self.assertEqual(blog["etag"], '"feed-v1"')
        self.assertIsNotNone(blog["last_success_at"])
        self.assertIsNone(blog["last_error"])

    @patch("app.feed_collector.urlopen")
    def test_handles_not_modified(self, urlopen):
        urlopen.side_effect = HTTPError(
            "https://example.com/feed.xml", 304, "Not Modified", {}, BytesIO()
        )

        result = collect_blog(self.database_path, self.blog_id)

        self.assertEqual(result["status"], "not_modified")
        self.assertEqual(result["saved"], 0)

    @patch("app.feed_collector.urlopen")
    def test_records_collection_failure(self, urlopen):
        urlopen.side_effect = URLError("network unavailable")

        with self.assertRaises(CollectionError):
            collect_blog(self.database_path, self.blog_id)

        blog = get_blog(self.database_path, self.blog_id)
        self.assertIn("network unavailable", blog["last_error"])
        self.assertIsNotNone(blog["last_checked_at"])

    def test_admin_sync_requires_api_key(self):
        response = self.client.post("/api/admin/sync")
        self.assertEqual(response.status_code, 401)

    @patch("app.routes.admin_sync.collect_all")
    def test_admin_sync_all(self, collect_all_mock):
        collect_all_mock.return_value = {
            "total": 1,
            "succeeded": 1,
            "failed": 0,
            "saved": 1,
            "results": [],
        }

        response = self.client.post(
            "/api/admin/sync",
            headers={"X-API-Key": "test-admin-key"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["ok"])
        self.assertEqual(response.json["saved"], 1)

    def test_admin_sync_returns_404_for_unknown_blog(self):
        response = self.client.post(
            "/api/admin/sync/9999",
            headers={"X-API-Key": "test-admin-key"},
        )
        self.assertEqual(response.status_code, 404)

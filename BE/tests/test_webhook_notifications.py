import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import connect, upsert_articles, upsert_blog
from app.discord_webhook import notify_subscription_webhooks


class WebhookNotificationTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.tempdir.name) / "test.db")
        self.app = create_app({
            "TESTING": True,
            "APP_ENV": "testing",
            "DATABASE_PATH": self.database_path,
            "SECRET_KEY": "test-secret",
        })
        self.client = self.app.test_client()
        self.client.post("/api/auth/register", json={
            "email": "webhook@example.com",
            "password": "password123",
            "display_name": "Webhook",
        })
        response = self.client.post("/api/auth/login", json={
            "email": "webhook@example.com",
            "password": "password123",
        })
        self.headers = {"Authorization": f"Bearer {response.json['token']}"}

    def tearDown(self):
        self.tempdir.cleanup()

    def test_validates_webhook_url(self):
        response = self.client.post(
            "/api/subscriptions",
            headers=self.headers,
            json={"keyword": "Python", "discord_webhook_url": "http://localhost/hook"},
        )
        self.assertEqual(response.status_code, 400)

    @patch("app.discord_webhook.send_webhook")
    def test_sends_matching_article_only_once(self, send_webhook):
        response = self.client.post(
            "/api/subscriptions",
            headers=self.headers,
            json={
                "keyword": "Python",
                "discord_webhook_url": "https://discord.com/api/webhooks/1/token",
            },
        )
        self.assertEqual(response.status_code, 201)
        blog_id = upsert_blog(self.database_path, {
            "name": "테스트 블로그",
            "company": "테스트",
            "feed_url": "https://example.com/rss",
            "site_url": "https://example.com",
        })
        upsert_articles(self.database_path, [{
            "blog_id": blog_id,
            "entry_key": "article-1",
            "title": "Python 비동기 처리",
            "url": "https://example.com/1",
            "fetched_at": "2026-01-01T00:00:00+00:00",
        }])
        with connect(self.database_path) as db:
            article_id = db.execute("SELECT id FROM articles").fetchone()["id"]

        first = notify_subscription_webhooks(self.database_path, [article_id])
        second = notify_subscription_webhooks(self.database_path, [article_id])

        self.assertEqual(first, {"matched": 1, "sent": 1, "failed": 0})
        self.assertEqual(second, {"matched": 0, "sent": 0, "failed": 0})
        send_webhook.assert_called_once()


if __name__ == "__main__":
    unittest.main()

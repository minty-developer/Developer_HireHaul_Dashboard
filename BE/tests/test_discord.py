import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nacl.signing import SigningKey

from app import create_app
from app.db import connect, upsert_articles, upsert_blog
from app.discord_bot import notify_new_articles


class DiscordInteractionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.signing_key = SigningKey.generate()
        self.app = create_app({
            "TESTING": True,
            "APP_ENV": "testing",
            "DATABASE_PATH": str(Path(self.temp.name) / "test.db"),
            "ADMIN_API_KEY": "test-admin-key",
            "CORS_ORIGINS": "http://localhost:3000",
            "DISCORD_PUBLIC_KEY": self.signing_key.verify_key.encode().hex(),
        })
        self.client = self.app.test_client()
        blog_id = upsert_blog(self.app.config["DATABASE_PATH"], {
            "name": "Example Tech",
            "company": "Example",
            "feed_url": "https://example.com/feed.xml",
            "site_url": "https://example.com",
        })
        upsert_articles(self.app.config["DATABASE_PATH"], [{
            "blog_id": blog_id,
            "entry_key": "python-1",
            "title": "Python 서비스 운영기",
            "url": "https://example.com/python",
            "summary": "Flask 백엔드",
            "fetched_at": "2026-10-08T00:00:00+00:00",
        }])
        with connect(self.app.config["DATABASE_PATH"]) as db:
            self.article_id = db.execute("SELECT id FROM articles").fetchone()[0]

    def tearDown(self):
        self.temp.cleanup()

    def post_interaction(self, payload, valid=True):
        body = json.dumps(payload, separators=(",", ":")).encode()
        timestamp = "1700000000"
        signature = self.signing_key.sign(timestamp.encode() + body).signature.hex()
        if not valid:
            signature = "00" * 64
        return self.client.post(
            "/api/discord/interactions",
            data=body,
            content_type="application/json",
            headers={
                "X-Signature-Ed25519": signature,
                "X-Signature-Timestamp": timestamp,
            },
        )

    def command(self, name, options=None, permissions="32"):
        return {
            "type": 2,
            "guild_id": "guild-1",
            "channel_id": "channel-1",
            "member": {"permissions": permissions, "user": {"id": "user-1"}},
            "data": {"name": name, "options": options or []},
        }

    def test_verifies_signature_and_answers_ping(self):
        response = self.post_interaction({"type": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"type": 1})
        self.assertEqual(self.post_interaction({"type": 1}, valid=False).status_code, 401)

    def test_configures_channel_and_manages_subscriptions(self):
        configured = self.post_interaction(self.command(
            "알림채널", [{"name": "channel", "value": "alerts-1"}]
        ))
        self.assertIn("alerts-1", configured.json["data"]["content"])

        added = self.post_interaction(self.command(
            "구독추가", [{"name": "keyword", "value": "Python"}]
        ))
        self.assertIn("구독했습니다", added.json["data"]["content"])
        listed = self.post_interaction(self.command("구독목록"))
        self.assertIn("Python", listed.json["data"]["content"])
        deleted = self.post_interaction(self.command(
            "구독삭제", [{"name": "keyword", "value": "python"}]
        ))
        self.assertIn("삭제했습니다", deleted.json["data"]["content"])

    def test_searches_articles(self):
        response = self.post_interaction(self.command(
            "검색", [{"name": "keyword", "value": "Flask"}]
        ))
        self.assertIn("Python 서비스 운영기", response.json["data"]["content"])

    @patch("app.discord_bot.send_channel_message")
    def test_sends_new_article_notification_only_once(self, send_message):
        self.post_interaction(self.command(
            "알림채널", [{"name": "channel", "value": "alerts-1"}]
        ))
        self.post_interaction(self.command(
            "구독추가", [{"name": "keyword", "value": "Python"}]
        ))
        first = notify_new_articles(
            self.app.config["DATABASE_PATH"], [self.article_id], "bot-token"
        )
        second = notify_new_articles(
            self.app.config["DATABASE_PATH"], [self.article_id], "bot-token"
        )
        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()

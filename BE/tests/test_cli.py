import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.db import connect


class CliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "APP_ENV": "testing",
            "DATABASE_PATH": str(Path(self.temp.name) / "test.db"),
            "ADMIN_API_KEY": "test-admin-key",
            "CORS_ORIGINS": "http://localhost:3000",
        })
        self.runner = self.app.test_cli_runner()

    def tearDown(self):
        self.temp.cleanup()

    @patch("app.collect_all")
    def test_collect_feeds_command(self, collect_all_mock):
        collect_all_mock.return_value = {
            "total": 1,
            "succeeded": 1,
            "failed": 0,
            "saved": 3,
            "results": [],
        }
        result = self.runner.invoke(args=["collect-feeds", "--timeout", "5"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(json.loads(result.output)["saved"], 3)
        collect_all_mock.assert_called_once_with(self.app.config["DATABASE_PATH"], timeout=5)

    @patch("app.collect_all")
    def test_collect_feeds_command_fails_when_a_feed_fails(self, collect_all_mock):
        collect_all_mock.return_value = {
            "total": 1,
            "succeeded": 0,
            "failed": 1,
            "saved": 0,
            "results": [],
        }
        result = self.runner.invoke(args=["collect-feeds"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("1개 블로그 수집에 실패", result.output)

    def test_prunes_expired_auth_tokens(self):
        client = self.app.test_client()
        client.post("/api/auth/register", json={
            "email": "user@example.com",
            "password": "password123",
            "display_name": "tester",
        })
        client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "password123",
        })
        with connect(self.app.config["DATABASE_PATH"]) as db:
            db.execute(
                "UPDATE auth_tokens SET expires_at = '2000-01-01T00:00:00+00:00'"
            )

        result = self.runner.invoke(args=["prune-auth-tokens"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("1개", result.output)
        with connect(self.app.config["DATABASE_PATH"]) as db:
            count = db.execute("SELECT COUNT(*) FROM auth_tokens").fetchone()[0]
        self.assertEqual(count, 0)

    def test_prunes_old_login_attempts(self):
        with connect(self.app.config["DATABASE_PATH"]) as db:
            db.execute(
                "INSERT INTO login_attempts VALUES ('old', 5, 1), ('recent', 1, 9999999999)"
            )
        result = self.runner.invoke(args=["prune-login-attempts"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("1개", result.output)
        with connect(self.app.config["DATABASE_PATH"]) as db:
            keys = [row[0] for row in db.execute("SELECT attempt_key FROM login_attempts")]
        self.assertEqual(keys, ["recent"])


if __name__ == "__main__":
    unittest.main()

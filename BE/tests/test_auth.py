import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from app import create_app
from app.db import connect


class AuthApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "APP_ENV": "testing",
            "DATABASE_PATH": str(Path(self.temp.name) / "test.db"),
            "ADMIN_API_KEY": "test-admin-key",
            "AUTH_TOKEN_TTL_SECONDS": 3600,
            "AUTH_LOGIN_MAX_ATTEMPTS": 2,
            "AUTH_LOGIN_WINDOW_SECONDS": 300,
            "CORS_ORIGINS": "http://localhost:3000",
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def register(self, **overrides):
        body = {
            "email": "user@example.com",
            "password": "password123",
            "display_name": "테스터",
            **overrides,
        }
        return self.client.post("/api/auth/register", json=body)

    def login(self, **overrides):
        body = {
            "email": "user@example.com",
            "password": "password123",
            **overrides,
        }
        return self.client.post("/api/auth/login", json=body)

    def test_registers_user_without_exposing_password_hash(self):
        response = self.register(email=" User@Example.com ")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["user"]["email"], "user@example.com")
        self.assertNotIn("password_hash", response.json["user"])
        with connect(self.app.config["DATABASE_PATH"]) as db:
            saved = db.execute("SELECT * FROM users").fetchone()
        self.assertNotEqual(saved["password_hash"], "password123")

    def test_rejects_duplicate_email_case_insensitively(self):
        self.assertEqual(self.register().status_code, 201)
        response = self.register(email="USER@example.com")
        self.assertEqual(response.status_code, 409)

    def test_validates_registration_fields(self):
        self.assertEqual(self.register(email="invalid").status_code, 400)
        self.assertEqual(self.register(password="short").status_code, 400)
        self.assertEqual(self.register(display_name="").status_code, 400)

    def test_login_me_and_logout(self):
        self.register()
        login = self.login()

        self.assertEqual(login.status_code, 200)
        token = login.json["token"]
        headers = {"Authorization": f"Bearer {token}"}
        me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json["user"]["email"], "user@example.com")

        logout = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def test_rejects_bad_credentials_and_missing_token(self):
        self.register()
        self.assertEqual(self.login(password="wrong-password").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_rate_limits_repeated_login_failures(self):
        self.register()
        self.assertEqual(self.login(password="wrong-one").status_code, 401)
        self.assertEqual(self.login(password="wrong-two").status_code, 401)
        limited = self.login()
        self.assertEqual(limited.status_code, 429)
        self.assertGreater(int(limited.headers["Retry-After"]), 0)

    def test_successful_login_clears_failure_count(self):
        self.register()
        self.assertEqual(self.login(password="wrong-one").status_code, 401)
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.login(password="wrong-two").status_code, 401)
        self.assertEqual(self.login().status_code, 200)

    def test_database_stores_only_token_hash(self):
        self.register()
        token = self.login().json["token"]
        with connect(self.app.config["DATABASE_PATH"]) as db:
            saved = db.execute("SELECT token_hash FROM auth_tokens").fetchone()
        self.assertNotEqual(saved["token_hash"], token)
        self.assertEqual(len(saved["token_hash"]), 64)

    def test_updates_display_name(self):
        self.register()
        token = self.login().json["token"]
        response = self.client.patch(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"display_name": "새 이름"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["user"]["display_name"], "새 이름")

    def test_changes_password_and_revokes_existing_tokens(self):
        self.register()
        token = self.login().json["token"]
        headers = {"Authorization": f"Bearer {token}"}
        wrong = self.client.put(
            "/api/auth/password",
            headers=headers,
            json={"current_password": "wrong-password", "new_password": "new-password123"},
        )
        self.assertEqual(wrong.status_code, 401)

        changed = self.client.put(
            "/api/auth/password",
            headers=headers,
            json={"current_password": "password123", "new_password": "new-password123"},
        )
        self.assertEqual(changed.status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.login(password="new-password123").status_code, 200)

    def test_deletes_account_and_owned_data(self):
        self.register()
        token = self.login().json["token"]
        headers = {"Authorization": f"Bearer {token}"}
        self.client.post(
            "/api/subscriptions", headers=headers, json={"keyword": "Python"}
        )
        denied = self.client.delete(
            "/api/auth/me", headers=headers, json={"password": "wrong-password"}
        )
        self.assertEqual(denied.status_code, 401)

        deleted = self.client.delete(
            "/api/auth/me", headers=headers, json={"password": "password123"}
        )
        self.assertEqual(deleted.status_code, 204)
        with connect(self.app.config["DATABASE_PATH"]) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0], 0)

    @patch("app.routes.auth.send_email")
    def test_verifies_email_and_can_require_verification(self, send_email_mock):
        self.app.config.update({
            "SMTP_HOST": "smtp.test",
            "MAIL_FROM": "noreply@example.com",
            "REQUIRE_EMAIL_VERIFICATION": True,
        })
        registered = self.register()
        self.assertTrue(registered.json["verification_sent"])
        self.assertEqual(self.login().status_code, 403)

        body = send_email_mock.call_args.args[3]
        url = body.splitlines()[-1]
        token = parse_qs(urlparse(url).query)["token"][0]
        confirmed = self.client.post(
            "/api/auth/email/verification/confirm", json={"token": token}
        )
        self.assertEqual(confirmed.status_code, 204)
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/auth/email/verification/confirm", json={"token": token}
            ).status_code,
            400,
        )

    @patch("app.routes.auth.send_email")
    def test_resets_password_without_revealing_unknown_email(self, send_email_mock):
        self.register()
        self.app.config.update({"SMTP_HOST": "smtp.test", "MAIL_FROM": "noreply@example.com"})
        unknown = self.client.post(
            "/api/auth/password/reset/request", json={"email": "missing@example.com"}
        )
        self.assertEqual(unknown.status_code, 202)

        requested = self.client.post(
            "/api/auth/password/reset/request", json={"email": "user@example.com"}
        )
        self.assertEqual(requested.status_code, 202)
        body = send_email_mock.call_args.args[3]
        token = parse_qs(urlparse(body.splitlines()[-1]).query)["token"][0]
        reset = self.client.post(
            "/api/auth/password/reset/confirm",
            json={"token": token, "new_password": "reset-password123"},
        )
        self.assertEqual(reset.status_code, 204)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.login(password="reset-password123").status_code, 200)


if __name__ == "__main__":
    unittest.main()

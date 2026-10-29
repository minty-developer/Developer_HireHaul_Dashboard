import tempfile
import unittest
from pathlib import Path

from app import create_app


class SubscriptionApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "APP_ENV": "testing",
            "DATABASE_PATH": str(Path(self.temp.name) / "test.db"),
            "ADMIN_API_KEY": "test-admin-key",
            "AUTH_TOKEN_TTL_SECONDS": 3600,
            "CORS_ORIGINS": "http://localhost:3000",
        })
        self.client = self.app.test_client()
        self.first_headers = self._register_and_login("first@example.com")
        self.second_headers = self._register_and_login("second@example.com")

    def tearDown(self):
        self.temp.cleanup()

    def _register_and_login(self, email):
        self.client.post("/api/auth/register", json={
            "email": email,
            "password": "password123",
            "display_name": email.split("@")[0],
        })
        response = self.client.post("/api/auth/login", json={
            "email": email,
            "password": "password123",
        })
        return {"Authorization": f"Bearer {response.json['token']}"}

    def test_requires_authentication(self):
        self.assertEqual(self.client.get("/api/subscriptions").status_code, 401)
        self.assertEqual(
            self.client.post("/api/subscriptions", json={"keyword": "Python"}).status_code,
            401,
        )

    def test_creates_and_lists_own_subscriptions(self):
        created = self.client.post(
            "/api/subscriptions",
            headers=self.first_headers,
            json={"keyword": "  Python   Backend  "},
        )
        self.client.post(
            "/api/subscriptions",
            headers=self.second_headers,
            json={"keyword": "React"},
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json["subscription"]["keyword"], "Python Backend")
        listed = self.client.get("/api/subscriptions", headers=self.first_headers)
        self.assertEqual(len(listed.json["subscriptions"]), 1)
        self.assertEqual(listed.json["subscriptions"][0]["keyword"], "Python Backend")

    def test_rejects_invalid_and_case_insensitive_duplicate_keyword(self):
        self.assertEqual(
            self.client.post(
                "/api/subscriptions", headers=self.first_headers, json={"keyword": ""}
            ).status_code,
            400,
        )
        self.client.post(
            "/api/subscriptions", headers=self.first_headers, json={"keyword": "Python"}
        )
        duplicate = self.client.post(
            "/api/subscriptions", headers=self.first_headers, json={"keyword": "python"}
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_deletes_only_own_subscription(self):
        created = self.client.post(
            "/api/subscriptions", headers=self.first_headers, json={"keyword": "Flask"}
        )
        subscription_id = created.json["subscription"]["id"]

        denied = self.client.delete(
            f"/api/subscriptions/{subscription_id}", headers=self.second_headers
        )
        self.assertEqual(denied.status_code, 404)
        deleted = self.client.delete(
            f"/api/subscriptions/{subscription_id}", headers=self.first_headers
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(
            self.client.delete(
                f"/api/subscriptions/{subscription_id}", headers=self.first_headers
            ).status_code,
            404,
        )

    def test_updates_own_webhook_and_can_disable_it(self):
        created = self.client.post(
            "/api/subscriptions", headers=self.first_headers, json={"keyword": "Flask"}
        )
        subscription_id = created.json["subscription"]["id"]
        endpoint = f"/api/subscriptions/{subscription_id}"
        webhook_url = "https://discord.com/api/webhooks/123/secret-token"

        self.assertEqual(
            self.client.patch(
                endpoint,
                headers=self.second_headers,
                json={"discord_webhook_url": webhook_url},
            ).status_code,
            404,
        )
        updated = self.client.patch(
            endpoint,
            headers=self.first_headers,
            json={"discord_webhook_url": webhook_url},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["subscription"]["discord_webhook_url"], webhook_url)
        self.assertEqual(
            self.client.patch(
                endpoint,
                headers=self.first_headers,
                json={"discord_webhook_url": "https://discord.com:444/api/webhooks/1/x"},
            ).status_code,
            400,
        )
        disabled = self.client.patch(
            endpoint,
            headers=self.first_headers,
            json={"discord_webhook_url": None},
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertIsNone(disabled.json["subscription"]["discord_webhook_url"])

    def test_toggles_only_own_subscription_and_validates_active(self):
        created = self.client.post(
            "/api/subscriptions", headers=self.first_headers, json={"keyword": "Flask"}
        )
        endpoint = f"/api/subscriptions/{created.json['subscription']['id']}"
        self.assertEqual(created.json["subscription"]["active"], 1)

        self.assertEqual(self.client.patch(
            endpoint, headers=self.second_headers, json={"active": False}
        ).status_code, 404)
        self.assertEqual(self.client.patch(
            endpoint, headers=self.first_headers, json={"active": 0}
        ).status_code, 400)
        self.assertEqual(self.client.patch(
            endpoint, headers=self.first_headers, json={}
        ).status_code, 400)

        paused = self.client.patch(
            endpoint, headers=self.first_headers, json={"active": False}
        )
        self.assertEqual(paused.status_code, 200)
        self.assertEqual(paused.json["subscription"]["active"], 0)
        resumed = self.client.patch(
            endpoint, headers=self.first_headers, json={"active": True}
        )
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json["subscription"]["active"], 1)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from app import create_app


class AdminBlogsApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "APP_ENV": "testing",
            "DATABASE_PATH": str(Path(self.temp.name) / "test.db"),
            "ADMIN_API_KEY": "test-admin-key",
            "CORS_ORIGINS": "http://localhost:3000",
        })
        self.client = self.app.test_client()
        self.headers = {"X-API-Key": "test-admin-key"}
        self.payload = {
            "name": "Example Tech",
            "company": "Example",
            "feed_url": "https://example.com/feed.xml",
            "site_url": "https://example.com/tech",
            "description": "Example engineering blog",
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_requires_admin_key(self):
        self.assertEqual(self.client.get("/api/admin/blogs").status_code, 401)
        self.assertEqual(self.client.post("/api/admin/blogs", json=self.payload).status_code, 401)

    def test_create_list_update_and_deactivate_blog(self):
        created = self.client.post("/api/admin/blogs", headers=self.headers, json=self.payload)
        self.assertEqual(created.status_code, 201)
        blog_id = created.json["blog"]["id"]

        updated = self.client.patch(
            f"/api/admin/blogs/{blog_id}",
            headers=self.headers,
            json={"name": "Updated Tech", "active": True},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["blog"]["name"], "Updated Tech")

        deleted = self.client.delete(f"/api/admin/blogs/{blog_id}", headers=self.headers)
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get(f"/api/blogs/{blog_id}").status_code, 404)

        listed = self.client.get("/api/admin/blogs", headers=self.headers)
        self.assertEqual(listed.json["blogs"][0]["active"], 0)

    def test_validates_payload_and_duplicate_feed(self):
        invalid = self.client.post(
            "/api/admin/blogs",
            headers=self.headers,
            json={**self.payload, "feed_url": "file:///etc/passwd"},
        )
        self.assertEqual(invalid.status_code, 400)
        self.client.post("/api/admin/blogs", headers=self.headers, json=self.payload)
        duplicate = self.client.post(
            "/api/admin/blogs",
            headers=self.headers,
            json={**self.payload, "name": "Duplicate"},
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_returns_404_for_unknown_blog(self):
        response = self.client.patch(
            "/api/admin/blogs/9999", headers=self.headers, json={"active": True}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.client.delete("/api/admin/blogs/9999", headers=self.headers).status_code,
            404,
        )

    def test_returns_operational_status(self):
        response = self.client.get("/api/admin/status", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")
        self.assertIn("articles", response.json["counts"])
        self.assertGreater(response.json["database_size_bytes"], 0)


if __name__ == "__main__":
    unittest.main()

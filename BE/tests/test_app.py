import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import create_app
from app.db import upsert_jobs


class AppTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "APP_ENV": "testing",
            "DATABASE_PATH": str(Path(self.temp.name) / "test.db"),
            "SYNC_API_KEY": "test-key",
            "CORS_ORIGINS": "http://localhost:3000",
        })
        self.client = self.app.test_client()
        self.auth = {"X-API-Key": "test-key"}

    def tearDown(self):
        self.temp.cleanup()

    def test_health_and_sample_sync(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/api/health").json["status"], "ok")
        self.assertEqual(self.client.get("/api/health").json["database"], "ok")
        result = self.client.post("/api/sync", json={}, headers=self.auth)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["source"], "sample")
        self.assertEqual(self.client.get("/api/jobs").json["count"], 3)

    def test_search(self):
        self.client.post("/api/sync", json={}, headers=self.auth)
        data = self.client.get("/api/jobs?q=Flask").json
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["total"], 1)

    def test_sync_requires_auth_when_key_is_configured(self):
        response = self.client.post("/api/sync", json={})
        self.assertEqual(response.status_code, 401)

    def test_sync_validates_body_and_count(self):
        for body in ([], {"count": 0}, {"count": 201}, {"count": "invalid"}):
            with self.subTest(body=body):
                response = self.client.post("/api/sync", json=body, headers=self.auth)
                self.assertEqual(response.status_code, 400)

    def test_jobs_validates_pagination(self):
        for query in ("limit=0", "limit=201", "limit=invalid", "offset=-1"):
            with self.subTest(query=query):
                response = self.client.get(f"/api/jobs?{query}")
                self.assertEqual(response.status_code, 400)

    def test_jobs_pagination(self):
        self.client.post("/api/sync", json={}, headers=self.auth)
        first_page = self.client.get("/api/jobs?limit=2&offset=0").json
        second_page = self.client.get("/api/jobs?limit=2&offset=2").json
        self.assertEqual(first_page["count"], 2)
        self.assertEqual(first_page["total"], 3)
        self.assertEqual(second_page["count"], 1)

    def test_expired_jobs_are_excluded_from_jobs_and_stats(self):
        now = datetime.now(timezone.utc)
        upsert_jobs(self.app.config["DATABASE_PATH"], [{
            "source": "test",
            "external_id": "expired-1",
            "title": "Expired job",
            "company": "Test company",
            "location": "Seoul",
            "experience": "",
            "education": "",
            "employment_type": "",
            "salary": "",
            "url": "https://example.com/expired-1",
            "posted_at": (now - timedelta(days=2)).isoformat(),
            "expires_at": (now - timedelta(days=1)).isoformat(),
            "keywords": "test",
            "active": 1,
            "fetched_at": now.isoformat(),
        }])

        self.assertEqual(self.client.get("/api/jobs").json["total"], 0)
        self.assertEqual(self.client.get("/api/stats").json["total"], 0)

    def test_production_requires_secure_configuration(self):
        with self.assertRaises(RuntimeError):
            create_app({
                "APP_ENV": "production",
                "DATABASE_PATH": str(Path(self.temp.name) / "production.db"),
                "SECRET_KEY": "change-me",
                "SYNC_API_KEY": "",
            })


if __name__ == "__main__":
    unittest.main()

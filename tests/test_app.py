import tempfile
import unittest
from pathlib import Path

from app import create_app


class AppTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE_PATH": str(Path(self.temp.name) / "test.db")})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_health_and_sample_sync(self):
        self.assertEqual(self.client.get("/").status_code, 404)
        self.assertEqual(self.client.get("/api/health").json["status"], "ok")
        result = self.client.post("/api/sync", json={})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["source"], "sample")
        self.assertEqual(self.client.get("/api/jobs").json["count"], 3)

    def test_search(self):
        self.client.post("/api/sync", json={})
        data = self.client.get("/api/jobs?q=Flask").json
        self.assertEqual(data["count"], 1)


if __name__ == "__main__":
    unittest.main()

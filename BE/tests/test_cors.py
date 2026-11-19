import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import create_app
from app.config import load_config
from app.logging_config import JsonFormatter

ORIGIN = "https://minty-developer.github.io"


class CorsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with patch.dict(os.environ, {"CORS_ORIGINS": f" {ORIGIN}/ , http://localhost:3000/ , {ORIGIN}, "}):
            with self.assertLogs("app", level="INFO") as logs:
                self.app = create_app({
                    "TESTING": True,
                    "APP_ENV": "testing",
                    "DATABASE_PATH": str(Path(self.temp.name) / "test.db"),
                })
        self.startup_logs = logs.records
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_effective_config_and_safe_startup_log(self):
        self.assertEqual(self.app.state.config["CORS_ORIGINS"], f"{ORIGIN},http://localhost:3000")
        entry = json.loads(JsonFormatter().format(self.startup_logs[0]))
        self.assertEqual(entry["message"], "cors_configured")
        self.assertEqual(entry["cors_origins"], [ORIGIN, "http://localhost:3000"])
        self.assertEqual(entry["process_id"], os.getpid())
        self.assertNotIn("SECRET_KEY", entry)

    def test_get_allowed_origin_and_request_log(self):
        with self.assertLogs("app", level="INFO") as logs:
            response = self.client.get("/api/articles", headers={"Origin": ORIGIN, "X-Request-ID": "cors-check"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], ORIGIN)
        self.assertIn("origin", response.headers["vary"].lower())
        entry = json.loads(JsonFormatter().format(logs.records[-1]))
        self.assertTrue(entry["cors_origin_allowed"])
        self.assertEqual(entry["request_id"], "cors-check")
        self.assertEqual(entry["process_id"], os.getpid())

    def test_preflight_allowed_origin(self):
        response = self.client.options("/api/articles", headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], ORIGIN)
        self.assertIn("GET", response.headers["access-control-allow-methods"])
        self.assertIn("authorization", response.headers["access-control-allow-headers"].lower())

    def test_disallowed_origin(self):
        for origin in ("https://untrusted.example", ORIGIN + ".evil.example"):
            with self.subTest(origin=origin):
                response = self.client.get("/api/articles", headers={"Origin": origin})
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("access-control-allow-origin", response.headers)
                response = self.client.options("/api/articles", headers={
                    "Origin": origin, "Access-Control-Request-Method": "GET",
                })
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("access-control-allow-origin", response.headers)

    def test_no_origin_and_error_response(self):
        response = self.client.get("/api/articles")
        self.assertNotIn("access-control-allow-origin", response.headers)
        response = self.client.get("/api/articles", headers={"Origin": ORIGIN, "Content-Length": "999999999"})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers["access-control-allow-origin"], ORIGIN)

    def test_invalid_origins_do_not_leak_input(self):
        for value in (
            ORIGIN + "/repo", ORIGIN + "?token=private",
            "https://user:private@example.com", "https://@example.com",
            "https://:@example.com", "example.com", "https://example.com:bad",
        ):
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError) as error:
                    load_config({"CORS_ORIGINS": value})
                self.assertNotIn(value, str(error.exception))

    def test_production_rejects_empty_normalized_list(self):
        with self.assertRaisesRegex(RuntimeError, "Production requires CORS_ORIGINS"):
            load_config({"APP_ENV": "production", "SECRET_KEY": "secure-test-secret",
                         "ADMIN_API_KEY": "test-key", "CORS_ORIGINS": " , , "})

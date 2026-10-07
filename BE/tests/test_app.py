import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import connect, upsert_articles, upsert_blog
from app.seed_blogs import DEFAULT_BLOGS, seed_default_blogs


class AppTest(unittest.TestCase):
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

    def tearDown(self):
        self.temp.cleanup()

    def test_home(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tech Blog Aggregator", response.data)

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok", "database": "ok"})

    def test_api_errors_and_security_headers(self):
        missing = self.client.get("/api/does-not-exist")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.content_type, "application/json")

        wrong_method = self.client.put("/api/health")
        self.assertEqual(wrong_method.status_code, 405)
        self.assertEqual(wrong_method.content_type, "application/json")

        auth = self.client.post("/api/auth/login", json={})
        self.assertEqual(auth.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(auth.headers["X-Frame-Options"], "DENY")
        self.assertEqual(auth.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(auth.headers["Cache-Control"], "no-store")

    def test_database_schema_is_created(self):
        with connect(self.app.config["DATABASE_PATH"]) as db:
            tables = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

        self.assertTrue(
            {
                "blogs", "articles", "users", "auth_tokens", "subscriptions",
                "schema_migrations", "login_attempts",
            }.issubset(tables)
        )
        with connect(self.app.config["DATABASE_PATH"]) as db:
            versions = [
                row["version"]
                for row in db.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
            ]
        self.assertEqual(versions, [1, 2])

    def test_blog_and_article_upsert(self):
        database_path = self.app.config["DATABASE_PATH"]
        blog_id = upsert_blog(database_path, {
            "name": "Engineering Blog",
            "company": "Example",
            "feed_url": "https://example.com/feed.xml",
            "site_url": "https://example.com/tech",
        })
        same_blog_id = upsert_blog(database_path, {
            "name": "Updated Engineering Blog",
            "company": "Example",
            "feed_url": "https://example.com/feed.xml",
            "site_url": "https://example.com/engineering",
        })
        article = {
            "blog_id": blog_id,
            "entry_key": "article-1",
            "title": "First title",
            "url": "https://example.com/tech/article-1",
            "fetched_at": "2026-10-06T12:00:00+09:00",
        }

        self.assertEqual(blog_id, same_blog_id)
        self.assertEqual(upsert_articles(database_path, [article]), 1)
        self.assertEqual(
            upsert_articles(database_path, [{**article, "title": "Updated title"}]),
            1,
        )

        with connect(database_path) as db:
            blog = db.execute("SELECT * FROM blogs").fetchone()
            saved_article = db.execute("SELECT * FROM articles").fetchone()

        self.assertEqual(blog["name"], "Updated Engineering Blog")
        self.assertEqual(saved_article["title"], "Updated title")
        self.assertEqual(saved_article["blog_id"], blog_id)

    def test_deleting_blog_deletes_its_articles(self):
        database_path = self.app.config["DATABASE_PATH"]
        blog_id = upsert_blog(database_path, {
            "name": "Engineering Blog",
            "company": "Example",
            "feed_url": "https://example.com/feed.xml",
            "site_url": "https://example.com/tech",
        })
        upsert_articles(database_path, [{
            "blog_id": blog_id,
            "entry_key": "article-1",
            "title": "Article",
            "url": "https://example.com/article-1",
            "fetched_at": "2026-10-06T12:00:00+09:00",
        }])

        with connect(database_path) as db:
            db.execute("DELETE FROM blogs WHERE id = ?", (blog_id,))

        with connect(database_path) as db:
            count = db.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

        self.assertEqual(count, 0)

    def test_seed_default_blogs_is_repeatable(self):
        database_path = self.app.config["DATABASE_PATH"]

        self.assertEqual(seed_default_blogs(database_path), len(DEFAULT_BLOGS))
        self.assertEqual(seed_default_blogs(database_path), len(DEFAULT_BLOGS))

        with connect(database_path) as db:
            blogs = db.execute("SELECT * FROM blogs ORDER BY id").fetchall()

        self.assertEqual(len(blogs), len(DEFAULT_BLOGS))
        self.assertTrue(all(blog["active"] == 1 for blog in blogs))

    def test_production_requires_secure_configuration(self):
        with self.assertRaises(RuntimeError):
            create_app({
                "APP_ENV": "production",
                "DATABASE_PATH": str(Path(self.temp.name) / "production.db"),
                "SECRET_KEY": "change-me",
                "ADMIN_API_KEY": "test-admin-key",
                "CORS_ORIGINS": "https://example.com",
            })

        with self.assertRaises(RuntimeError):
            create_app({
                "APP_ENV": "production",
                "DATABASE_PATH": str(Path(self.temp.name) / "production.db"),
                "SECRET_KEY": "a-secure-production-secret",
                "ADMIN_API_KEY": "",
                "CORS_ORIGINS": "https://example.com",
            })


if __name__ == "__main__":
    unittest.main()

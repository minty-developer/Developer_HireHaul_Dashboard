import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app
from app.db import MIGRATIONS, connect, upsert_articles, upsert_blog
from app.security import hash_password, verify_password


def article(blog_id, key, title, summary="", content="", published="2026-10-01"):
    return {
        "blog_id": blog_id,
        "entry_key": key,
        "title": title,
        "url": f"https://example.com/{key}",
        "summary": summary,
        "content": content,
        "published_at": f"{published}T00:00:00+00:00",
        "fetched_at": "2026-10-06T00:00:00+00:00",
    }


class ArticleSearchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp.name) / "test.db")
        self.app = create_app({
            "TESTING": True,
            "APP_ENV": "testing",
            "DATABASE_PATH": self.database_path,
            "ADMIN_API_KEY": "test-admin-key",
        })
        self.client = TestClient(self.app)
        self.kakao = upsert_blog(self.database_path, {
            "name": "Kakao Tech", "company": "카카오",
            "feed_url": "https://kakao.example/feed", "site_url": "https://kakao.example",
        })
        self.naver = upsert_blog(self.database_path, {
            "name": "NAVER D2", "company": "네이버",
            "feed_url": "https://naver.example/feed", "site_url": "https://naver.example",
        })
        upsert_articles(self.database_path, [
            article(self.kakao, "k1", "쿠버네티스 운영 가이드", "클러스터 모니터링", published="2026-10-03"),
            article(self.kakao, "k2", "Kafka 이벤트 처리", "쿠버네티스 위에서 Kafka 운영", published="2026-10-04"),
            article(self.naver, "n1", "검색 엔진 개선기", "형태소 분석과 색인", published="2026-10-02"),
            article(self.naver, "n2", "100% 할인_이벤트 회고", "마케팅 시스템", published="2026-10-01"),
        ])

    def tearDown(self):
        self.temp.cleanup()

    def search(self, query):
        response = self.client.get(f"/api/articles?{query}")
        self.assertEqual(response.status_code, 200, response.text)
        return [item["title"] for item in response.json()["articles"]]

    def test_korean_substring_uses_full_text_index(self):
        self.assertEqual(
            sorted(self.search("q=쿠버네티스")),
            ["Kafka 이벤트 처리", "쿠버네티스 운영 가이드"],
        )
        self.assertEqual(self.search("q=버네티"), self.search("q=쿠버네티스"))

    def test_multiple_terms_must_all_match(self):
        self.assertEqual(self.search("q=쿠버네티스 Kafka"), ["Kafka 이벤트 처리"])
        self.assertEqual(self.search("q=쿠버네티스 없는단어"), [])

    def test_short_terms_fall_back_to_like(self):
        self.assertEqual(self.search("q=검색"), ["검색 엔진 개선기"])
        self.assertEqual(self.search("q=색인 검색"), ["검색 엔진 개선기"])

    def test_search_is_case_insensitive(self):
        self.assertEqual(self.search("q=kafka"), ["Kafka 이벤트 처리"])

    def test_like_wildcards_are_literal(self):
        self.assertEqual(self.search("q=%25"), ["100% 할인_이벤트 회고"])
        self.assertEqual(self.search("q=_"), ["100% 할인_이벤트 회고"])

    def test_fts_syntax_is_treated_as_text(self):
        for query in ('q="', "q=AND", "q=a*b", "q=NOT OR", "q=-(x)"):
            with self.subTest(query=query):
                self.client.get(f"/api/articles?{query}").raise_for_status()

    def test_relevance_sort_prefers_title_match(self):
        self.assertEqual(
            self.search("q=쿠버네티스&sort=relevance")[0], "쿠버네티스 운영 가이드"
        )
        self.assertEqual(self.search("q=쿠버네티스")[0], "Kafka 이벤트 처리")
        self.assertEqual(self.client.get("/api/articles?sort=random").status_code, 400)

    def test_filters_by_company(self):
        self.assertEqual(
            sorted(self.search("company=네이버")),
            ["100% 할인_이벤트 회고", "검색 엔진 개선기"],
        )

    def test_index_follows_updates_and_deletes(self):
        upsert_articles(self.database_path, [
            article(self.kakao, "k1", "서비스 메시 도입기", "Istio 적용", published="2026-10-03"),
        ])
        self.assertEqual(self.search("q=서비스 메시"), ["서비스 메시 도입기"])
        self.assertEqual(self.search("q=쿠버네티스"), ["Kafka 이벤트 처리"])
        with connect(self.database_path) as db:
            db.execute("DELETE FROM articles WHERE entry_key = 'k2'")
        self.assertEqual(self.search("q=Kafka"), [])

    def test_inactive_blog_is_excluded(self):
        with connect(self.database_path) as db:
            db.execute("UPDATE blogs SET active = 0 WHERE id = ?", (self.naver,))
        self.assertEqual(self.search("q=검색"), [])

    def test_validation_errors_are_readable(self):
        response = self.client.get("/api/articles?limit=0")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"ok": False, "error": "limit은 1~100, offset은 0 이상의 정수여야 합니다."},
        )


class MigrationCompatibilityTest(unittest.TestCase):
    def test_existing_articles_are_indexed_when_upgrading(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "old.db")
            # 7번 마이그레이션까지 적용된 기존 Flask 시절 DB를 만든다.
            with sqlite3.connect(path) as db:
                db.execute(
                    "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY,"
                    " name TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
                for version, name, sql in MIGRATIONS[:7]:
                    db.executescript(sql)
                    db.execute("INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                               (version, name))
                db.execute(
                    "INSERT INTO blogs (name, company, feed_url, site_url)"
                    " VALUES ('B', 'C', 'https://e.com/f', 'https://e.com')"
                )
                db.execute(
                    "INSERT INTO articles (blog_id, entry_key, title, url, fetched_at)"
                    " VALUES (1, 'old', '기존 게시글 데이터베이스', 'https://e.com/1', 'now')"
                )
                db.execute(
                    "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
                    ("old@example.com", "scrypt:32768:8:1$abcdEFGH12345678$"
                     + hashlib.scrypt(b"password123", salt=b"abcdEFGH12345678",
                                      n=32768, r=8, p=1, maxmem=132 * 32768 * 8).hex(),
                     "old"),
                )
            db.close()

            client = TestClient(create_app({"TESTING": True, "DATABASE_PATH": path}))
            found = client.get("/api/articles?q=데이터베이스").json()
            self.assertEqual(found["total"], 1)
            login = client.post("/api/auth/login", json={
                "email": "old@example.com", "password": "password123",
            })
            self.assertEqual(login.status_code, 200)
            client.close()


class PasswordHashTest(unittest.TestCase):
    def test_hash_round_trip_and_rejects_garbage(self):
        stored = hash_password("비밀번호123")
        self.assertTrue(stored.startswith("scrypt:32768:8:1$"))
        self.assertTrue(verify_password(stored, "비밀번호123"))
        self.assertFalse(verify_password(stored, "wrong"))
        self.assertFalse(verify_password("not-a-hash", "wrong"))


class ApiDocsTest(unittest.TestCase):
    def test_swagger_ui_and_security_schemes(self):
        with tempfile.TemporaryDirectory() as temp:
            client = TestClient(create_app({
                "TESTING": True, "DATABASE_PATH": str(Path(temp) / "t.db"),
            }))
            self.assertEqual(client.get("/api/docs").status_code, 200)
            spec = client.get("/api/openapi.json").json()
            self.assertIn("HTTPBearer", spec["components"]["securitySchemes"])
            self.assertIn("APIKeyHeader", spec["components"]["securitySchemes"])
            client.close()


if __name__ == "__main__":
    unittest.main()

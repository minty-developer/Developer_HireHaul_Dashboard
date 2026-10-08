from __future__ import annotations

import sqlite3
from contextlib import contextmanager


SCHEMA = """
CREATE TABLE IF NOT EXISTS blogs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    company TEXT NOT NULL,
    feed_url TEXT NOT NULL UNIQUE,
    site_url TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    etag TEXT,
    last_modified TEXT,
    last_checked_at TEXT,
    last_success_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blog_id INTEGER NOT NULL,
    entry_key TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    published_at TEXT,
    feed_updated_at TEXT,
    fetched_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (blog_id) REFERENCES blogs(id) ON DELETE CASCADE,
    UNIQUE (blog_id, entry_key)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    keyword TEXT NOT NULL COLLATE NOCASE,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_blogs_active
ON blogs(active);

CREATE INDEX IF NOT EXISTS idx_articles_blog_published
ON articles(blog_id, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_articles_published
ON articles(published_at DESC);

CREATE INDEX IF NOT EXISTS idx_auth_tokens_user
ON auth_tokens(user_id);

CREATE INDEX IF NOT EXISTS idx_auth_tokens_expires
ON auth_tokens(expires_at);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user
ON subscriptions(user_id, active);

"""

LOGIN_ATTEMPTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS login_attempts (
    attempt_key TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL,
    window_started_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_window
ON login_attempts(window_started_at);
"""

EMAIL_AUTH_SCHEMA = """
ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0
    CHECK (email_verified IN (0, 1));

CREATE TABLE auth_action_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    purpose TEXT NOT NULL CHECK (purpose IN ('verify_email', 'reset_password')),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_auth_action_tokens_user_purpose
ON auth_action_tokens(user_id, purpose, used_at);

CREATE INDEX idx_auth_action_tokens_expires
ON auth_action_tokens(expires_at);
"""

MIGRATIONS = (
    (1, "initial_schema", SCHEMA),
    (2, "login_attempts", LOGIN_ATTEMPTS_SCHEMA),
    (3, "email_auth", EMAIL_AUTH_SCHEMA),
)


@contextmanager
def connect(path: str):
    connection = sqlite3.connect(path, timeout=10)

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")

    try:
        yield connection
        connection.commit()

    finally:
        connection.close()


def init_db(path: str) -> None:
    with connect(path) as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied = {
            row["version"]
            for row in db.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for version, name, sql in MIGRATIONS:
            if version in applied:
                continue
            safe_name = name.replace("'", "''")
            db.executescript(
                f"BEGIN IMMEDIATE;\n{sql}\n"
                f"INSERT INTO schema_migrations (version, name) "
                f"VALUES ({version}, '{safe_name}');\nCOMMIT;"
            )


def upsert_blog(path: str, blog: dict) -> int:
    sql = """
    INSERT INTO blogs (
        name, company, feed_url, site_url, description, active
    ) VALUES (
        :name, :company, :feed_url, :site_url, :description, :active
    )
    ON CONFLICT(feed_url) DO UPDATE SET
        name = excluded.name,
        company = excluded.company,
        site_url = excluded.site_url,
        description = excluded.description,
        active = excluded.active,
        updated_at = CURRENT_TIMESTAMP
    """

    values = {
        "description": "",
        "active": 1,
        **blog,
    }
    with connect(path) as db:
        db.execute(sql, values)
        row = db.execute(
            "SELECT id FROM blogs WHERE feed_url = ?",
            (values["feed_url"],),
        ).fetchone()

    return int(row["id"])


def upsert_articles(path: str, articles: list[dict]) -> int:
    if not articles:
        return 0

    sql = """
    INSERT INTO articles (
        blog_id, entry_key, title, url, author, summary, content,
        published_at, feed_updated_at, fetched_at
    ) VALUES (
        :blog_id, :entry_key, :title, :url, :author, :summary, :content,
        :published_at, :feed_updated_at, :fetched_at
    )
    ON CONFLICT(blog_id, entry_key) DO UPDATE SET
        title = excluded.title,
        url = excluded.url,
        author = excluded.author,
        summary = excluded.summary,
        content = excluded.content,
        published_at = excluded.published_at,
        feed_updated_at = excluded.feed_updated_at,
        fetched_at = excluded.fetched_at,
        updated_at = CURRENT_TIMESTAMP
    """

    defaults = {
        "author": "",
        "summary": "",
        "content": "",
        "published_at": None,
        "feed_updated_at": None,
    }
    rows = [{**defaults, **article} for article in articles]

    with connect(path) as db:
        db.executemany(sql, rows)

    return len(rows)


def get_blog(path: str, blog_id: int) -> dict | None:
    with connect(path) as db:
        row = db.execute(
            "SELECT * FROM blogs WHERE id = ?",
            (blog_id,),
        ).fetchone()
    return dict(row) if row else None


def get_active_blogs(path: str) -> list[dict]:
    with connect(path) as db:
        rows = db.execute(
            "SELECT * FROM blogs WHERE active = 1 ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def update_blog_sync_status(
    path: str,
    blog_id: int,
    *,
    checked_at: str,
    succeeded: bool,
    etag: str | None = None,
    last_modified: str | None = None,
    error: str | None = None,
) -> None:
    if succeeded:
        sql = """
        UPDATE blogs
        SET last_checked_at = ?,
            last_success_at = ?,
            last_error = NULL,
            etag = COALESCE(?, etag),
            last_modified = COALESCE(?, last_modified),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """
        values = (checked_at, checked_at, etag, last_modified, blog_id)
    else:
        sql = """
        UPDATE blogs
        SET last_checked_at = ?,
            last_error = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """
        values = (checked_at, error or "알 수 없는 수집 오류", blog_id)

    with connect(path) as db:
        db.execute(sql, values)

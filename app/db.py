from __future__ import annotations

import sqlite3
from contextlib import contextmanager


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    experience TEXT NOT NULL DEFAULT '',
    education TEXT NOT NULL DEFAULT '',
    employment_type TEXT NOT NULL DEFAULT '',
    salary TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    posted_at TEXT,
    expires_at TEXT,
    keywords TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    fetched_at TEXT NOT NULL,
    UNIQUE(source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_active_expires ON jobs(active, expires_at);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
"""


@contextmanager
def connect(path: str):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db(path: str) -> None:
    with connect(path) as db:
        db.executescript(SCHEMA)


def upsert_jobs(path: str, jobs: list[dict]) -> int:
    sql = """
    INSERT INTO jobs (source, external_id, title, company, location, experience,
      education, employment_type, salary, url, posted_at, expires_at, keywords,
      active, fetched_at)
    VALUES (:source, :external_id, :title, :company, :location, :experience,
      :education, :employment_type, :salary, :url, :posted_at, :expires_at,
      :keywords, :active, :fetched_at)
    ON CONFLICT(source, external_id) DO UPDATE SET
      title=excluded.title, company=excluded.company, location=excluded.location,
      experience=excluded.experience, education=excluded.education,
      employment_type=excluded.employment_type, salary=excluded.salary,
      url=excluded.url, posted_at=excluded.posted_at, expires_at=excluded.expires_at,
      keywords=excluded.keywords, active=excluded.active, fetched_at=excluded.fetched_at
    """
    with connect(path) as db:
        db.executemany(sql, jobs)
    return len(jobs)


from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path


def backup_database(database_path: str, backup_directory: str) -> Path:
    source_path = Path(database_path)
    directory = Path(backup_directory)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = directory / f"tech_blog_{timestamp}.db"
    suffix = 1
    while target.exists():
        target = directory / f"tech_blog_{timestamp}_{suffix}.db"
        suffix += 1

    with closing(sqlite3.connect(source_path)) as source:
        with closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
    return target


def restore_database(database_path: str, backup_path: str) -> None:
    source_path = Path(backup_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError("백업 파일을 찾을 수 없습니다.")
    target_path = Path(database_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source_path)) as source:
        result = source.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise ValueError("유효한 SQLite 백업 파일이 아닙니다.")
        with closing(sqlite3.connect(target_path)) as destination:
            source.backup(destination)


def prune_backups(backup_directory: str, retention_days: int) -> int:
    directory = Path(backup_directory)
    if not directory.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    removed = 0
    for path in directory.glob("tech_blog_*.db"):
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        if modified < cutoff:
            path.unlink()
            removed += 1
    return removed

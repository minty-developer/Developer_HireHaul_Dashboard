from pathlib import Path

from fastapi import APIRouter

from ..db import connect
from ..deps import AdminOnly, DatabasePath

router = APIRouter(tags=["admin"], dependencies=[AdminOnly])


@router.get("/api/admin/status", summary="DB·수집 운영 상태")
def admin_status(database_path: DatabasePath):
    with connect(database_path) as db:
        counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("blogs", "articles", "users", "subscriptions")
        }
        sync = db.execute(
            """
            SELECT MAX(last_checked_at) AS last_checked_at,
                   MAX(last_success_at) AS last_success_at,
                   SUM(CASE WHEN last_error IS NOT NULL THEN 1 ELSE 0 END) AS failed_blogs
            FROM blogs
            """
        ).fetchone()
    return {
        "status": "ok",
        "database_size_bytes": Path(database_path).stat().st_size,
        "counts": counts,
        "sync": dict(sync),
    }

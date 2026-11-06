import sqlite3

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..db import connect
from ..deps import DatabasePath
from ..logging_config import logger

router = APIRouter(tags=["health"])


@router.get("/api/health", summary="서버와 데이터베이스 상태 확인")
def health(database_path: DatabasePath):
    try:
        with connect(database_path) as db:
            db.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        logger.exception("Database health check failed")
        return JSONResponse({"status": "error", "database": "unavailable"}, status_code=503)
    return {"status": "ok", "database": "ok"}

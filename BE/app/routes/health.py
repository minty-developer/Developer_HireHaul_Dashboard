import sqlite3

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..db import connect
from ..deps import Config, DatabasePath
from ..mailer import email_enabled
from ..logging_config import logger
from ..schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/api/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "DB 연결 실패"}},
    summary="서버와 데이터베이스 상태 확인",
)
def health(database_path: DatabasePath, config: Config):
    email = "enabled" if email_enabled(config) else "disabled"
    try:
        with connect(database_path) as db:
            db.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        logger.exception("Database health check failed")
        return JSONResponse(
            {"status": "error", "database": "unavailable", "email": email}, status_code=503
        )
    return {"status": "ok", "database": "ok", "email": email}

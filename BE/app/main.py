from __future__ import annotations

import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from .config import cors_origins, load_config
from .db import init_db
from .errors import HTTP_MESSAGES, register_error_handlers
from .logging_config import configure_logging, logger
from .routes import router
from .schemas import ErrorResponse

NO_STORE_PREFIXES = ("/api/auth", "/api/admin", "/api/subscriptions")


def create_app(test_config: dict | None = None) -> FastAPI:
    config = load_config(test_config)
    Path(config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    init_db(config["DATABASE_PATH"])
    configure_logging(config)

    app = FastAPI(
        title="Tech Blog Aggregator API",
        version="2.0.0",
        description="국내 IT 기업 기술 블로그 RSS 수집·검색·키워드 구독 API",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    app.state.config = config

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        started = time.perf_counter()
        request_id = request.headers.get("X-Request-ID", "")[:100] or uuid.uuid4().hex

        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > config["MAX_CONTENT_LENGTH"]:
            response = JSONResponse({"error": HTTP_MESSAGES[413]}, status_code=413)
        else:
            response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith(NO_STORE_PREFIXES):
            response.headers.setdefault("Cache-Control", "no-store")
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response

    # 나중에 추가한 미들웨어가 바깥쪽에서 실행되므로 CORS 응답에도 위 헤더가 붙는다.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(config),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(router)
    app.openapi = lambda: _openapi(app)
    return app


ERROR_SCHEMA_REF = {"$ref": "#/components/schemas/ErrorResponse"}


def _error_response(description: str) -> dict:
    return {"description": description, "content": {"application/json": {"schema": ERROR_SCHEMA_REF}}}


def _openapi(app: FastAPI) -> dict:
    """문서를 실제 응답과 맞춘다.

    FastAPI는 검증 실패를 422로 문서화하지만, errors.py의 핸들러가 400
    `{"ok": false, "error": "..."}`로 바꿔 보내므로 문서도 400으로 고친다.
    """
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)
    components["ErrorResponse"] = ErrorResponse.model_json_schema()

    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            responses = operation.get("responses", {})
            if responses.pop("422", None) is not None:
                responses.setdefault("400", _error_response("입력값 오류"))
            security = {name for item in operation.get("security", []) for name in item}
            if "HTTPBearer" in security:
                responses.setdefault("401", _error_response("토큰 없음 또는 만료"))
            if "APIKeyHeader" in security:
                responses.setdefault("401", _error_response("관리자 인증 실패"))
    app.openapi_schema = schema
    return schema

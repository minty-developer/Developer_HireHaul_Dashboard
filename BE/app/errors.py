from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """라우트·의존성 어디서든 던지면 지정한 JSON 본문으로 응답한다."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        ok_field: bool = False,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.payload = {"ok": False, "error": message} if ok_field else {"error": message}
        self.headers = headers


HTTP_MESSAGES = {
    404: "요청한 API를 찾을 수 없습니다.",
    405: "허용되지 않은 요청 방식입니다.",
    413: "요청 본문이 너무 큽니다.",
}

# 타입 오류처럼 직접 메시지를 지정하지 않은 검증 실패에 쓰는 필드별 안내
FIELD_MESSAGES = {
    "limit": "limit은 1~100, offset은 0 이상의 정수여야 합니다.",
    "offset": "limit은 1~100, offset은 0 이상의 정수여야 합니다.",
    "blog_id": "blog_id는 1 이상의 정수여야 합니다.",
    "sort": "sort는 latest 또는 relevance여야 합니다.",
    "q": "검색어는 200자 이하여야 합니다.",
    "active": "active는 boolean이어야 합니다.",
    "discord_webhook_url": "유효한 Discord 웹훅 URL이 아닙니다.",
}


def validation_message(errors: list[dict]) -> str:
    if not errors:
        return "요청 값이 올바르지 않습니다."
    error = errors[0]
    loc = [str(part) for part in error.get("loc", ())]
    if error.get("type") == "value_error":
        return str(error.get("msg", "")).removeprefix("Value error, ")
    if loc[:1] == ["body"] and (len(loc) == 1 or error.get("type") == "json_invalid"):
        return "JSON 요청 본문이 필요합니다."
    field = loc[-1] if loc else ""
    if error.get("type") == "missing":
        return f"{field}은(는) 필수입니다."
    return FIELD_MESSAGES.get(field, f"{field} 값이 올바르지 않습니다.")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError):
        return JSONResponse(exc.payload, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            {"ok": False, "error": validation_message(list(exc.errors()))},
            status_code=400,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        headers = getattr(exc, "headers", None)
        if request.url.path.startswith("/api/") or exc.status_code == 413:
            message = HTTP_MESSAGES.get(exc.status_code, str(exc.detail))
            return JSONResponse({"error": message}, status_code=exc.status_code, headers=headers)
        return PlainTextResponse(str(exc.detail), status_code=exc.status_code, headers=headers)

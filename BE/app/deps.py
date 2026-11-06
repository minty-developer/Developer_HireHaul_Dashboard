"""라우트에서 공통으로 쓰는 FastAPI 의존성."""
from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from .auth import get_user_for_token
from .errors import ApiError

# auto_error=False: 인증 실패 응답 형식을 직접 정하기 위해 FastAPI 기본 403을 끈다.
# 이 객체들은 /api/docs 의 Authorize 버튼에도 쓰인다.
bearer_scheme = HTTPBearer(auto_error=False, description="로그인 시 받은 토큰")
admin_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False, description="관리자 API 키")


def get_config(request: Request) -> dict:
    return request.app.state.config


Config = Annotated[dict, Depends(get_config)]


def get_database_path(config: Config) -> str:
    return config["DATABASE_PATH"]


DatabasePath = Annotated[str, Depends(get_database_path)]


def get_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str | None:
    if credentials is None or not credentials.credentials.strip():
        return None
    return credentials.credentials.strip()


BearerToken = Annotated[str | None, Depends(get_bearer_token)]


def get_current_user(token: BearerToken, database_path: DatabasePath) -> dict:
    if token is None:
        raise ApiError(401, "인증 토큰이 필요합니다.")
    user = get_user_for_token(database_path, token)
    if user is None:
        raise ApiError(401, "유효하지 않거나 만료된 인증 토큰입니다.")
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_admin(
    config: Config,
    supplied: Annotated[str | None, Depends(admin_key_scheme)],
) -> None:
    expected = config.get("ADMIN_API_KEY", "")
    if not (expected and hmac.compare_digest(supplied or "", expected)):
        raise ApiError(401, "관리자 인증에 실패했습니다.", ok_field=True)


AdminOnly = Depends(require_admin)

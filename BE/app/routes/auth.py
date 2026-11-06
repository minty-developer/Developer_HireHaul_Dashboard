from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Request, Response

from ..auth import (
    authenticate,
    change_password,
    clear_login_failures,
    consume_action_token,
    create_user,
    delete_user,
    find_user_by_email,
    issue_action_token,
    issue_token,
    login_attempt_key,
    login_retry_after,
    mark_email_verified,
    record_login_failure,
    revoke_token,
    update_display_name,
)
from ..deps import BearerToken, Config, CurrentUser
from ..errors import ApiError
from ..logging_config import logger
from ..mailer import send_email
from ..schemas import (
    DisplayNameRequest,
    EmailRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordRequest,
    PasswordResetConfirmRequest,
    RegisterRequest,
    TokenRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

PUBLIC_USER_FIELDS = ("id", "email", "display_name", "email_verified", "created_at")


def _send_action_email(config: dict, user: dict, purpose: str) -> bool:
    ttl_key = (
        "EMAIL_VERIFICATION_TTL_SECONDS"
        if purpose == "verify_email"
        else "PASSWORD_RESET_TTL_SECONDS"
    )
    token, _expires_at = issue_action_token(
        config["DATABASE_PATH"], user["id"], purpose, config[ttl_key]
    )
    if purpose == "verify_email":
        subject, path = "이메일 인증 안내", "verify-email"
    else:
        subject, path = "비밀번호 재설정 안내", "reset-password"
    url = f"{config['PUBLIC_BASE_URL']}/{path}?token={token}"
    if config.get("TESTING") and not config.get("SMTP_HOST"):
        return True
    try:
        send_email(config, user["email"], subject, f"다음 링크를 열어주세요:\n{url}")
    except Exception:
        logger.exception("Email delivery failed for purpose=%s", purpose)
        return False
    return True


@router.post("/register", status_code=201, summary="회원가입")
def register(body: RegisterRequest, config: Config):
    try:
        user = create_user(
            config["DATABASE_PATH"], body.email, body.password, body.display_name
        )
    except sqlite3.IntegrityError:
        raise ApiError(409, "이미 가입된 이메일입니다.") from None
    verification_sent = _send_action_email(config, user, "verify_email")
    return {"user": user, "verification_sent": verification_sent}


@router.post("/login", summary="로그인 및 Bearer 토큰 발급")
def login(body: LoginRequest, request: Request, config: Config):
    database_path = config["DATABASE_PATH"]
    remote = request.client.host if request.client else "unknown"
    attempt_key = login_attempt_key(body.email, remote)
    retry_after = login_retry_after(
        database_path,
        attempt_key,
        config["AUTH_LOGIN_MAX_ATTEMPTS"],
        config["AUTH_LOGIN_WINDOW_SECONDS"],
    )
    if retry_after:
        raise ApiError(
            429,
            "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해주세요.",
            headers={"Retry-After": str(retry_after)},
        )

    user = authenticate(database_path, body.email, body.password)
    if user is None:
        record_login_failure(database_path, attempt_key, config["AUTH_LOGIN_WINDOW_SECONDS"])
        raise ApiError(401, "이메일 또는 비밀번호가 올바르지 않습니다.")
    if config["REQUIRE_EMAIL_VERIFICATION"] and not user["email_verified"]:
        raise ApiError(403, "이메일 인증이 필요합니다.")

    clear_login_failures(database_path, attempt_key)
    token, expires_at = issue_token(database_path, user["id"], config["AUTH_TOKEN_TTL_SECONDS"])
    return {
        "token": token,
        "expires_at": expires_at,
        "user": {key: user[key] for key in PUBLIC_USER_FIELDS},
    }


@router.get("/me", summary="로그인 사용자 조회")
def me(user: CurrentUser):
    return {"user": user}


@router.patch("/me", summary="표시 이름 수정")
def update_me(body: DisplayNameRequest, user: CurrentUser, config: Config):
    updated = update_display_name(config["DATABASE_PATH"], user["id"], body.display_name)
    return {"user": updated}


@router.put("/password", status_code=204, summary="비밀번호 변경 및 기존 토큰 폐기")
def update_password(body: PasswordChangeRequest, user: CurrentUser, config: Config):
    if authenticate(config["DATABASE_PATH"], user["email"], body.current_password) is None:
        raise ApiError(401, "현재 비밀번호가 올바르지 않습니다.")
    if body.current_password == body.new_password:
        raise ApiError(400, "새 비밀번호는 현재 비밀번호와 달라야 합니다.")
    change_password(config["DATABASE_PATH"], user["id"], body.new_password)
    return Response(status_code=204)


@router.delete("/me", status_code=204, summary="회원 탈퇴")
def remove_me(user: CurrentUser, config: Config, body: PasswordRequest | None = None):
    password = body.password if body else ""
    if authenticate(config["DATABASE_PATH"], user["email"], password) is None:
        raise ApiError(401, "비밀번호가 올바르지 않습니다.")
    delete_user(config["DATABASE_PATH"], user["id"])
    return Response(status_code=204)


@router.post("/logout", status_code=204, summary="현재 토큰 폐기")
def logout(_user: CurrentUser, token: BearerToken, config: Config):
    revoke_token(config["DATABASE_PATH"], token)
    return Response(status_code=204)


@router.post("/email/verification/request", status_code=202, summary="이메일 인증 메일 재요청")
def request_email_verification(config: Config, body: EmailRequest | None = None):
    user = find_user_by_email(config["DATABASE_PATH"], body.email if body else "")
    if user and not user["email_verified"]:
        _send_action_email(config, user, "verify_email")
    return {"message": "가입된 이메일이면 인증 안내를 전송했습니다."}


@router.post("/email/verification/confirm", status_code=204, summary="이메일 인증 확정")
def confirm_email_verification(config: Config, body: TokenRequest | None = None):
    user_id = consume_action_token(
        config["DATABASE_PATH"], body.token if body else "", "verify_email"
    )
    if user_id is None:
        raise ApiError(400, "유효하지 않거나 만료된 인증 토큰입니다.")
    mark_email_verified(config["DATABASE_PATH"], user_id)
    return Response(status_code=204)


@router.post("/password/reset/request", status_code=202, summary="비밀번호 재설정 메일 요청")
def request_password_reset(config: Config, body: EmailRequest | None = None):
    user = find_user_by_email(config["DATABASE_PATH"], body.email if body else "")
    if user:
        _send_action_email(config, user, "reset_password")
    return {"message": "가입된 이메일이면 재설정 안내를 전송했습니다."}


@router.post("/password/reset/confirm", status_code=204, summary="비밀번호 재설정 확정")
def confirm_password_reset(body: PasswordResetConfirmRequest, config: Config):
    user_id = consume_action_token(config["DATABASE_PATH"], body.token, "reset_password")
    if user_id is None:
        raise ApiError(400, "유효하지 않거나 만료된 재설정 토큰입니다.")
    change_password(config["DATABASE_PATH"], user_id, body.new_password)
    return Response(status_code=204)

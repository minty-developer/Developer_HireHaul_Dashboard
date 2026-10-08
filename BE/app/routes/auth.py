from __future__ import annotations

import sqlite3

from flask import current_app, jsonify, request

from app.auth import (
    authenticate,
    bearer_token,
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
    require_user,
    revoke_token,
    update_display_name,
)
from app.mailer import send_email

from . import bp


def _json_body() -> dict | None:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else None


def _send_action_email(user: dict, purpose: str) -> bool:
    config = current_app.config
    ttl_key = (
        "EMAIL_VERIFICATION_TTL_SECONDS"
        if purpose == "verify_email"
        else "PASSWORD_RESET_TTL_SECONDS"
    )
    token, _expires_at = issue_action_token(
        config["DATABASE_PATH"], user["id"], purpose, config[ttl_key]
    )
    if purpose == "verify_email":
        subject = "이메일 인증 안내"
        path = "verify-email"
    else:
        subject = "비밀번호 재설정 안내"
        path = "reset-password"
    url = f"{config['PUBLIC_BASE_URL']}/{path}?token={token}"
    if config.get("TESTING") and not config.get("SMTP_HOST"):
        return True
    try:
        send_email(config, user["email"], subject, f"다음 링크를 열어주세요:\n{url}")
    except Exception:
        current_app.logger.exception("Email delivery failed for purpose=%s", purpose)
        return False
    return True


@bp.post("/api/auth/register")
def register():
    body = _json_body()
    if body is None:
        return jsonify({"error": "JSON 요청 본문이 필요합니다."}), 400

    email = str(body.get("email", "")).strip()
    password = str(body.get("password", ""))
    display_name = str(body.get("display_name", "")).strip()
    if "@" not in email or len(email) > 254:
        return jsonify({"error": "올바른 이메일을 입력해주세요."}), 400
    if len(password) < 8 or len(password) > 128:
        return jsonify({"error": "비밀번호는 8~128자여야 합니다."}), 400
    if not display_name or len(display_name) > 50:
        return jsonify({"error": "표시 이름은 1~50자여야 합니다."}), 400

    try:
        user = create_user(
            current_app.config["DATABASE_PATH"], email, password, display_name
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "이미 가입된 이메일입니다."}), 409
    verification_sent = _send_action_email(user, "verify_email")
    return jsonify({"user": user, "verification_sent": verification_sent}), 201


@bp.post("/api/auth/login")
def login():
    body = _json_body()
    if body is None:
        return jsonify({"error": "JSON 요청 본문이 필요합니다."}), 400

    database_path = current_app.config["DATABASE_PATH"]
    email = str(body.get("email", ""))
    attempt_key = login_attempt_key(email, request.remote_addr or "unknown")
    retry_after = login_retry_after(
        database_path,
        attempt_key,
        current_app.config["AUTH_LOGIN_MAX_ATTEMPTS"],
        current_app.config["AUTH_LOGIN_WINDOW_SECONDS"],
    )
    if retry_after:
        response = jsonify({"error": "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해주세요."})
        response.headers["Retry-After"] = str(retry_after)
        return response, 429

    user = authenticate(database_path, email, str(body.get("password", "")))
    if user is None:
        record_login_failure(
            database_path, attempt_key, current_app.config["AUTH_LOGIN_WINDOW_SECONDS"]
        )
        return jsonify({"error": "이메일 또는 비밀번호가 올바르지 않습니다."}), 401

    if current_app.config["REQUIRE_EMAIL_VERIFICATION"] and not user["email_verified"]:
        return jsonify({"error": "이메일 인증이 필요합니다."}), 403

    clear_login_failures(database_path, attempt_key)

    token, expires_at = issue_token(
        database_path,
        user["id"],
        current_app.config["AUTH_TOKEN_TTL_SECONDS"],
    )
    public_user = {
        key: user[key]
        for key in ("id", "email", "display_name", "email_verified", "created_at")
    }
    return jsonify({"token": token, "expires_at": expires_at, "user": public_user})


@bp.get("/api/auth/me")
def me():
    user, error = require_user()
    if error:
        return jsonify(error[0]), error[1]
    return jsonify({"user": user})


@bp.patch("/api/auth/me")
def update_me():
    user, error = require_user()
    if error:
        return jsonify(error[0]), error[1]
    body = _json_body()
    display_name = str(body.get("display_name", "")).strip() if body else ""
    if not display_name or len(display_name) > 50:
        return jsonify({"error": "표시 이름은 1~50자여야 합니다."}), 400
    updated = update_display_name(
        current_app.config["DATABASE_PATH"], user["id"], display_name
    )
    return jsonify({"user": updated})


@bp.put("/api/auth/password")
def update_password():
    user, error = require_user()
    if error:
        return jsonify(error[0]), error[1]
    body = _json_body()
    if body is None:
        return jsonify({"error": "JSON 요청 본문이 필요합니다."}), 400
    current_password = str(body.get("current_password", ""))
    new_password = str(body.get("new_password", ""))
    if authenticate(current_app.config["DATABASE_PATH"], user["email"], current_password) is None:
        return jsonify({"error": "현재 비밀번호가 올바르지 않습니다."}), 401
    if len(new_password) < 8 or len(new_password) > 128:
        return jsonify({"error": "새 비밀번호는 8~128자여야 합니다."}), 400
    if current_password == new_password:
        return jsonify({"error": "새 비밀번호는 현재 비밀번호와 달라야 합니다."}), 400
    change_password(current_app.config["DATABASE_PATH"], user["id"], new_password)
    return "", 204


@bp.delete("/api/auth/me")
def remove_me():
    user, error = require_user()
    if error:
        return jsonify(error[0]), error[1]
    body = _json_body()
    password = str(body.get("password", "")) if body else ""
    if authenticate(current_app.config["DATABASE_PATH"], user["email"], password) is None:
        return jsonify({"error": "비밀번호가 올바르지 않습니다."}), 401
    delete_user(current_app.config["DATABASE_PATH"], user["id"])
    return "", 204


@bp.post("/api/auth/logout")
def logout():
    user, error = require_user()
    if error:
        return jsonify(error[0]), error[1]
    revoke_token(current_app.config["DATABASE_PATH"], bearer_token())
    return "", 204


@bp.post("/api/auth/email/verification/request")
def request_email_verification():
    body = _json_body()
    email = str(body.get("email", "")) if body else ""
    user = find_user_by_email(current_app.config["DATABASE_PATH"], email)
    if user and not user["email_verified"]:
        _send_action_email(user, "verify_email")
    return jsonify({"message": "가입된 이메일이면 인증 안내를 전송했습니다."}), 202


@bp.post("/api/auth/email/verification/confirm")
def confirm_email_verification():
    body = _json_body()
    token = str(body.get("token", "")) if body else ""
    user_id = consume_action_token(
        current_app.config["DATABASE_PATH"], token, "verify_email"
    )
    if user_id is None:
        return jsonify({"error": "유효하지 않거나 만료된 인증 토큰입니다."}), 400
    mark_email_verified(current_app.config["DATABASE_PATH"], user_id)
    return "", 204


@bp.post("/api/auth/password/reset/request")
def request_password_reset():
    body = _json_body()
    email = str(body.get("email", "")) if body else ""
    user = find_user_by_email(current_app.config["DATABASE_PATH"], email)
    if user:
        _send_action_email(user, "reset_password")
    return jsonify({"message": "가입된 이메일이면 재설정 안내를 전송했습니다."}), 202


@bp.post("/api/auth/password/reset/confirm")
def confirm_password_reset():
    body = _json_body()
    token = str(body.get("token", "")) if body else ""
    new_password = str(body.get("new_password", "")) if body else ""
    if len(new_password) < 8 or len(new_password) > 128:
        return jsonify({"error": "새 비밀번호는 8~128자여야 합니다."}), 400
    user_id = consume_action_token(
        current_app.config["DATABASE_PATH"], token, "reset_password"
    )
    if user_id is None:
        return jsonify({"error": "유효하지 않거나 만료된 재설정 토큰입니다."}), 400
    change_password(current_app.config["DATABASE_PATH"], user_id, new_password)
    return "", 204

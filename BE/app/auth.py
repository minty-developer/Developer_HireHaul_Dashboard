from __future__ import annotations

import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone

from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import connect


def normalize_email(value: str) -> str:
    return value.strip().lower()


def login_attempt_key(email: str, remote_address: str) -> str:
    value = f"{normalize_email(email)}\n{remote_address}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def login_retry_after(
    database_path: str,
    attempt_key: str,
    max_attempts: int,
    window_seconds: int,
) -> int:
    now = int(time.time())
    with connect(database_path) as db:
        row = db.execute(
            "SELECT attempts, window_started_at FROM login_attempts WHERE attempt_key = ?",
            (attempt_key,),
        ).fetchone()
        if row is None:
            return 0
        elapsed = now - row["window_started_at"]
        if elapsed >= window_seconds:
            db.execute("DELETE FROM login_attempts WHERE attempt_key = ?", (attempt_key,))
            return 0
        if row["attempts"] >= max_attempts:
            return max(1, window_seconds - elapsed)
    return 0


def record_login_failure(database_path: str, attempt_key: str, window_seconds: int) -> None:
    now = int(time.time())
    with connect(database_path) as db:
        row = db.execute(
            "SELECT window_started_at FROM login_attempts WHERE attempt_key = ?",
            (attempt_key,),
        ).fetchone()
        if row is None or now - row["window_started_at"] >= window_seconds:
            db.execute(
                """
                INSERT INTO login_attempts (attempt_key, attempts, window_started_at)
                VALUES (?, 1, ?)
                ON CONFLICT(attempt_key) DO UPDATE SET
                    attempts = 1,
                    window_started_at = excluded.window_started_at
                """,
                (attempt_key, now),
            )
        else:
            db.execute(
                "UPDATE login_attempts SET attempts = attempts + 1 WHERE attempt_key = ?",
                (attempt_key,),
            )


def clear_login_failures(database_path: str, attempt_key: str) -> None:
    with connect(database_path) as db:
        db.execute("DELETE FROM login_attempts WHERE attempt_key = ?", (attempt_key,))


def create_user(database_path: str, email: str, password: str, display_name: str) -> dict:
    with connect(database_path) as db:
        cursor = db.execute(
            """
            INSERT INTO users (email, password_hash, display_name)
            VALUES (?, ?, ?)
            """,
            (normalize_email(email), generate_password_hash(password), display_name.strip()),
        )
        user_id = cursor.lastrowid
        row = db.execute(
            "SELECT id, email, display_name, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row)


def authenticate(database_path: str, email: str, password: str) -> dict | None:
    with connect(database_path) as db:
        row = db.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE AND active = 1",
            (normalize_email(email),),
        ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        return None
    return dict(row)


def change_password(database_path: str, user_id: int, password: str) -> None:
    with connect(database_path) as db:
        db.execute(
            "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (generate_password_hash(password), user_id),
        )
        db.execute("DELETE FROM auth_tokens WHERE user_id = ?", (user_id,))


def update_display_name(database_path: str, user_id: int, display_name: str) -> dict:
    with connect(database_path) as db:
        db.execute(
            "UPDATE users SET display_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (display_name, user_id),
        )
        row = db.execute(
            "SELECT id, email, display_name, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row)


def delete_user(database_path: str, user_id: int) -> None:
    with connect(database_path) as db:
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))


def issue_token(database_path: str, user_id: int, ttl_seconds: int) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    token_hash = _token_hash(token)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    ).isoformat()
    with connect(database_path) as db:
        db.execute(
            "INSERT INTO auth_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user_id, token_hash, expires_at),
        )
    return token, expires_at


def revoke_token(database_path: str, token: str) -> None:
    with connect(database_path) as db:
        db.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (_token_hash(token),))


def get_user_for_token(database_path: str, token: str) -> dict | None:
    now = datetime.now(timezone.utc).isoformat()
    with connect(database_path) as db:
        row = db.execute(
            """
            SELECT users.id, users.email, users.display_name, users.created_at
            FROM auth_tokens
            JOIN users ON users.id = auth_tokens.user_id
            WHERE auth_tokens.token_hash = ?
              AND auth_tokens.expires_at > ?
              AND users.active = 1
            """,
            (_token_hash(token), now),
        ).fetchone()
    return dict(row) if row else None


def bearer_token() -> str | None:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def require_user() -> tuple[dict | None, tuple[dict, int] | None]:
    token = bearer_token()
    if token is None:
        return None, ({"error": "인증 토큰이 필요합니다."}, 401)
    user = get_user_for_token(current_app.config["DATABASE_PATH"], token)
    if user is None:
        return None, ({"error": "유효하지 않거나 만료된 인증 토큰입니다."}, 401)
    g.auth_token = token
    g.current_user = user
    return user, None


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

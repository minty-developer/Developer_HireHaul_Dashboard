from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INSECURE_SECRETS = {"", "dev-only-change-me", "change-me"}


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).lower() == "true"


def _int(name: str, default: str) -> int:
    return int(os.getenv(name, default))


def load_config(overrides: dict | None = None) -> dict:
    """환경변수에서 설정을 읽고, 테스트용 값이 있으면 덮어쓴 뒤 검증한다."""
    config = {
        "TESTING": False,
        "APP_ENV": os.getenv("APP_ENV", "development").lower(),
        "SECRET_KEY": os.getenv("SECRET_KEY", "dev-only-change-me"),
        "DATABASE_PATH": os.getenv("DATABASE_PATH", str(ROOT / "data" / "tech_blog.db")),
        "ADMIN_API_KEY": os.getenv("ADMIN_API_KEY", ""),
        "AUTH_TOKEN_TTL_SECONDS": _int("AUTH_TOKEN_TTL_SECONDS", "604800"),
        "AUTH_LOGIN_MAX_ATTEMPTS": _int("AUTH_LOGIN_MAX_ATTEMPTS", "5"),
        "AUTH_LOGIN_WINDOW_SECONDS": _int("AUTH_LOGIN_WINDOW_SECONDS", "300"),
        "MAX_CONTENT_LENGTH": _int("MAX_CONTENT_LENGTH", "1048576"),
        "FEED_COLLECTION_INTERVAL_SECONDS": _int("FEED_COLLECTION_INTERVAL_SECONDS", "3600"),
        "FEED_COLLECTION_TIMEOUT_SECONDS": _int("FEED_COLLECTION_TIMEOUT_SECONDS", "20"),
        "BACKUP_DIRECTORY": os.getenv("BACKUP_DIRECTORY", str(ROOT / "data" / "backups")),
        "BACKUP_RETENTION_DAYS": _int("BACKUP_RETENTION_DAYS", "14"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO").upper(),
        "REQUIRE_EMAIL_VERIFICATION": _bool("REQUIRE_EMAIL_VERIFICATION", "false"),
        "EMAIL_VERIFICATION_TTL_SECONDS": _int("EMAIL_VERIFICATION_TTL_SECONDS", "86400"),
        "PASSWORD_RESET_TTL_SECONDS": _int("PASSWORD_RESET_TTL_SECONDS", "1800"),
        "PUBLIC_BASE_URL": os.getenv("PUBLIC_BASE_URL", "http://localhost:3000").rstrip("/"),
        "MAIL_FROM": os.getenv("MAIL_FROM", ""),
        "SMTP_HOST": os.getenv("SMTP_HOST", ""),
        "SMTP_PORT": _int("SMTP_PORT", "587"),
        "SMTP_USERNAME": os.getenv("SMTP_USERNAME", ""),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", ""),
        "SMTP_USE_TLS": _bool("SMTP_USE_TLS", "true"),
        "SMTP_USE_SSL": _bool("SMTP_USE_SSL", "false"),
        "DISCORD_APPLICATION_ID": os.getenv("DISCORD_APPLICATION_ID", ""),
        "DISCORD_PUBLIC_KEY": os.getenv("DISCORD_PUBLIC_KEY", ""),
        "DISCORD_BOT_TOKEN": os.getenv("DISCORD_BOT_TOKEN", ""),
        "DISCORD_TEST_GUILD_ID": os.getenv("DISCORD_TEST_GUILD_ID", ""),
        "CORS_ORIGINS": os.getenv("CORS_ORIGINS", "http://localhost:3000"),
    }
    if overrides:
        config.update(overrides)
    _validate(config)
    return config


def _validate(config: dict) -> None:
    if config["APP_ENV"] != "production":
        return
    if config["SECRET_KEY"] in INSECURE_SECRETS:
        raise RuntimeError("Production requires a secure SECRET_KEY.")
    if not config["ADMIN_API_KEY"]:
        raise RuntimeError("Production requires ADMIN_API_KEY.")
    if not config["CORS_ORIGINS"]:
        raise RuntimeError("Production requires CORS_ORIGINS.")
    if config["REQUIRE_EMAIL_VERIFICATION"] and (
        not config["SMTP_HOST"] or not config["MAIL_FROM"]
    ):
        raise RuntimeError("Email verification requires SMTP_HOST and MAIL_FROM.")


def cors_origins(config: dict) -> list[str]:
    return [origin.strip() for origin in config["CORS_ORIGINS"].split(",") if origin.strip()]

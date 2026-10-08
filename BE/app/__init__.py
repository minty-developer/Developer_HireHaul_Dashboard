from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import Flask, g, jsonify, request
from flask_cors import CORS

from .db import connect, init_db
from .feed_collector import collect_all
from .logging_config import configure_logging
from .maintenance import backup_database, prune_backups, restore_database, run_scheduler
from .routes import bp
from .seed_blogs import seed_default_blogs


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=False,
        static_folder=None,
        template_folder=None,
    )

    # 프로젝트 루트 경로
    root = Path(__file__).resolve().parent.parent

    # 기본 설정
    app.config.from_mapping(
        APP_ENV=os.getenv("APP_ENV", "development").lower(),
        SECRET_KEY=os.getenv(
            "SECRET_KEY",
            "dev-only-change-me"
        ),
        DATABASE_PATH=os.getenv(
            "DATABASE_PATH",
            str(root / "data" / "tech_blog.db")
        ),
        ADMIN_API_KEY=os.getenv("ADMIN_API_KEY", ""),
        AUTH_TOKEN_TTL_SECONDS=int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "604800")),
        AUTH_LOGIN_MAX_ATTEMPTS=int(os.getenv("AUTH_LOGIN_MAX_ATTEMPTS", "5")),
        AUTH_LOGIN_WINDOW_SECONDS=int(os.getenv("AUTH_LOGIN_WINDOW_SECONDS", "300")),
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_CONTENT_LENGTH", "1048576")),
        FEED_COLLECTION_INTERVAL_SECONDS=int(os.getenv("FEED_COLLECTION_INTERVAL_SECONDS", "3600")),
        FEED_COLLECTION_TIMEOUT_SECONDS=int(os.getenv("FEED_COLLECTION_TIMEOUT_SECONDS", "20")),
        BACKUP_DIRECTORY=os.getenv("BACKUP_DIRECTORY", str(root / "data" / "backups")),
        BACKUP_RETENTION_DAYS=int(os.getenv("BACKUP_RETENTION_DAYS", "14")),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO").upper(),
        REQUIRE_EMAIL_VERIFICATION=os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").lower() == "true",
        EMAIL_VERIFICATION_TTL_SECONDS=int(os.getenv("EMAIL_VERIFICATION_TTL_SECONDS", "86400")),
        PASSWORD_RESET_TTL_SECONDS=int(os.getenv("PASSWORD_RESET_TTL_SECONDS", "1800")),
        PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL", "http://localhost:3000").rstrip("/"),
        MAIL_FROM=os.getenv("MAIL_FROM", ""),
        SMTP_HOST=os.getenv("SMTP_HOST", ""),
        SMTP_PORT=int(os.getenv("SMTP_PORT", "587")),
        SMTP_USERNAME=os.getenv("SMTP_USERNAME", ""),
        SMTP_PASSWORD=os.getenv("SMTP_PASSWORD", ""),
        SMTP_USE_TLS=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
        SMTP_USE_SSL=os.getenv("SMTP_USE_SSL", "false").lower() == "true",
        CORS_ORIGINS=os.getenv("CORS_ORIGINS", "http://localhost:3000"),
    )

    # 테스트용 설정이 있으면 덮어쓰기
    if test_config:
        app.config.update(test_config)

    if app.config["APP_ENV"] == "production":
        if app.config["SECRET_KEY"] in {"", "dev-only-change-me", "change-me"}:
            raise RuntimeError("Production requires a secure SECRET_KEY.")
        if not app.config["ADMIN_API_KEY"]:
            raise RuntimeError("Production requires ADMIN_API_KEY.")
        if not app.config["CORS_ORIGINS"]:
            raise RuntimeError("Production requires CORS_ORIGINS.")
        if app.config["REQUIRE_EMAIL_VERIFICATION"] and (
            not app.config["SMTP_HOST"] or not app.config["MAIL_FROM"]
        ):
            raise RuntimeError("Email verification requires SMTP_HOST and MAIL_FROM.")

    # API 경로에만 CORS를 적용하고 허용할 프론트엔드를 설정으로 제한한다.
    origins = [
        origin.strip()
        for origin in app.config["CORS_ORIGINS"].split(",")
        if origin.strip()
    ]
    CORS(app, resources={r"/api/*": {"origins": origins}})

    # DB 폴더가 없으면 생성
    Path(
        app.config["DATABASE_PATH"]
    ).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # DB 초기화
    init_db(
        app.config["DATABASE_PATH"]
    )

    # routes 폴더 안의 API 등록
    app.register_blueprint(bp)
    configure_logging(app)

    @app.before_request
    def start_request():
        g.request_started = time.perf_counter()
        g.request_id = request.headers.get("X-Request-ID", "")[:100] or uuid.uuid4().hex

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.path.startswith(("/api/auth", "/api/admin")):
            response.headers.setdefault("Cache-Control", "no-store")
        started = g.get("request_started")
        if started is not None:
            app.logger.info(
                "request_completed",
                extra={
                    "request_id": g.get("request_id"),
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
        return response

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "요청한 API를 찾을 수 없습니다."}), 404
        return "Not Found", 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "허용되지 않은 요청 방식입니다."}), 405
        return "Method Not Allowed", 405

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify({"error": "요청 본문이 너무 큽니다."}), 413

    @app.cli.command("seed-blogs")
    def seed_blogs_command() -> None:
        count = seed_default_blogs(app.config["DATABASE_PATH"])
        print(f"기본 기술 블로그 {count}개를 등록했습니다.")

    @app.cli.command("collect-feeds")
    @click.option("--timeout", type=click.IntRange(1, 120), default=20, show_default=True)
    def collect_feeds_command(timeout: int) -> None:
        """Collect every active blog feed once."""
        result = collect_all(app.config["DATABASE_PATH"], timeout=timeout)
        click.echo(json.dumps(result, ensure_ascii=False))
        if result["failed"]:
            raise click.ClickException(
                f"{result['failed']}개 블로그 수집에 실패했습니다."
            )

    @app.cli.command("prune-auth-tokens")
    def prune_auth_tokens_command() -> None:
        """Delete expired authentication tokens."""
        now = datetime.now(timezone.utc).isoformat()
        with connect(app.config["DATABASE_PATH"]) as db:
            cursor = db.execute(
                "DELETE FROM auth_tokens WHERE expires_at <= ?",
                (now,),
            )
            action_cursor = db.execute(
                "DELETE FROM auth_action_tokens WHERE expires_at <= ? OR used_at IS NOT NULL",
                (now,),
            )
        click.echo(
            f"만료된 인증 토큰 {cursor.rowcount}개와 인증 작업 토큰 "
            f"{action_cursor.rowcount}개를 삭제했습니다."
        )

    @app.cli.command("prune-login-attempts")
    def prune_login_attempts_command() -> None:
        """Delete expired login rate-limit records."""
        cutoff = int(datetime.now(timezone.utc).timestamp()) - app.config[
            "AUTH_LOGIN_WINDOW_SECONDS"
        ]
        with connect(app.config["DATABASE_PATH"]) as db:
            cursor = db.execute(
                "DELETE FROM login_attempts WHERE window_started_at <= ?", (cutoff,)
            )
        click.echo(f"오래된 로그인 시도 기록 {cursor.rowcount}개를 삭제했습니다.")

    @app.cli.command("backup-db")
    def backup_db_command() -> None:
        path = backup_database(app.config["DATABASE_PATH"], app.config["BACKUP_DIRECTORY"])
        removed = prune_backups(
            app.config["BACKUP_DIRECTORY"], app.config["BACKUP_RETENTION_DAYS"]
        )
        click.echo(f"백업을 생성했습니다: {path} (오래된 백업 {removed}개 삭제)")

    @app.cli.command("restore-db")
    @click.argument("backup_path", type=click.Path(exists=True, dir_okay=False))
    @click.option("--yes", is_flag=True, help="복원을 확인합니다.")
    def restore_db_command(backup_path: str, yes: bool) -> None:
        if not yes:
            raise click.ClickException("복원하려면 --yes 옵션이 필요합니다.")
        restore_database(app.config["DATABASE_PATH"], backup_path)
        click.echo("데이터베이스를 복원했습니다.")

    @app.cli.command("run-scheduler")
    def run_scheduler_command() -> None:
        def report(result: dict) -> None:
            app.logger.info(
                "scheduled_collection_completed",
                extra={
                    "total": result["total"],
                    "failed": result["failed"],
                    "saved": result["saved"],
                },
            )

        run_scheduler(
            collect_all,
            app.config["DATABASE_PATH"],
            app.config["BACKUP_DIRECTORY"],
            app.config["FEED_COLLECTION_INTERVAL_SECONDS"],
            app.config["FEED_COLLECTION_TIMEOUT_SECONDS"],
            app.config["BACKUP_RETENTION_DAYS"],
            report,
        )

    return app

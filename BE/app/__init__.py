from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import Flask, jsonify, request
from flask_cors import CORS

from .db import connect, init_db
from .feed_collector import collect_all
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

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.path.startswith(("/api/auth", "/api/admin")):
            response.headers.setdefault("Cache-Control", "no-store")
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
        with connect(app.config["DATABASE_PATH"]) as db:
            cursor = db.execute(
                "DELETE FROM auth_tokens WHERE expires_at <= ?",
                (datetime.now(timezone.utc).isoformat(),),
            )
        click.echo(f"만료된 인증 토큰 {cursor.rowcount}개를 삭제했습니다.")

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

    return app

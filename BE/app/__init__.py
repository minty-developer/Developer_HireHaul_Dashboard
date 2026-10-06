from __future__ import annotations

import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from .db import init_db
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

    @app.cli.command("seed-blogs")
    def seed_blogs_command() -> None:
        count = seed_default_blogs(app.config["DATABASE_PATH"])
        print(f"기본 기술 블로그 {count}개를 등록했습니다.")

    return app

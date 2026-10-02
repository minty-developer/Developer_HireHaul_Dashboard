from __future__ import annotations

import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from .db import init_db
from .routes import bp


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
        SECRET_KEY=os.getenv(
            "SECRET_KEY",
            "dev-only-change-me"
        ),
        DATABASE_PATH=os.getenv(
            "DATABASE_PATH",
            str(root / "data" / "jobs.db")
        ),
        DEFAULT_KEYWORDS=os.getenv(
            "DEFAULT_KEYWORDS",
            "Python,백엔드,프론트엔드,데이터"
        ),
        SYNC_API_KEY=os.getenv("SYNC_API_KEY", ""),
        CORS_ORIGINS=os.getenv("CORS_ORIGINS", "http://localhost:3000"),
    )

    # 테스트용 설정이 있으면 덮어쓰기
    if test_config:
        app.config.update(test_config)

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

    return app

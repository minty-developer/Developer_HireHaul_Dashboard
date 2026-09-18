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

    CORS(app)

    root = Path(__file__).resolve().parent.parent

    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
        DATABASE_PATH=os.getenv("DATABASE_PATH", str(root / "data" / "jobs.db")),
        DEFAULT_KEYWORDS=os.getenv(
            "DEFAULT_KEYWORDS",
            "Python,백엔드,프론트엔드,데이터"
        ),
    )

    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE_PATH"]).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    init_db(app.config["DATABASE_PATH"])
    app.register_blueprint(bp)

    return app
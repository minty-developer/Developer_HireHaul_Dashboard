from flask import current_app, jsonify, request

from . import bp
from ..db import upsert_jobs
from ..providers import SampleProvider


@bp.post("/api/sync")
def sync():

    body = request.get_json(silent=True) or {}

    keyword = str(
        body.get("keyword")
        or current_app.config["DEFAULT_KEYWORDS"]
    )

    try:

        provider = SampleProvider()

        fetched = provider.fetch(
            keyword,
            int(body.get("count", 50))
        )

        count = upsert_jobs(
            current_app.config["DATABASE_PATH"],
            fetched
        )

        return jsonify({
            "ok": True,
            "source": provider.name,
            "saved": count
        })

    except (ValueError, OSError, TimeoutError) as exc:

        return jsonify({
            "ok": False,
            "error": str(exc)
        }), 502
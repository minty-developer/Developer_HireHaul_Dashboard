import hmac

from flask import current_app, jsonify, request

from . import bp
from ..db import upsert_jobs
from ..providers import SampleProvider


@bp.post("/api/sync")
def sync():

    expected_key = current_app.config.get("SYNC_API_KEY", "")
    supplied_key = request.headers.get("X-API-Key", "")
    if expected_key and not hmac.compare_digest(supplied_key, expected_key):
        return jsonify({"ok": False, "error": "인증에 실패했습니다."}), 401

    if request.data and not request.is_json:
        return jsonify({"ok": False, "error": "JSON 본문이 필요합니다."}), 415

    body = request.get_json(silent=True) if request.data else {}
    if body is None:
        return jsonify({"ok": False, "error": "올바른 JSON 본문이 필요합니다."}), 400
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "JSON 본문은 객체여야 합니다."}), 400

    keyword = body.get("keyword") or current_app.config["DEFAULT_KEYWORDS"]
    if not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 200:
        return jsonify({"ok": False, "error": "keyword는 1~200자 문자열이어야 합니다."}), 400

    try:
        count = int(body.get("count", 50))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "count는 정수여야 합니다."}), 400

    if not 1 <= count <= 200:
        return jsonify({"ok": False, "error": "count는 1~200 범위여야 합니다."}), 400

    try:

        provider = SampleProvider()

        fetched = provider.fetch(
            keyword.strip(),
            count
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

        current_app.logger.exception("Job synchronization failed")

        return jsonify({
            "ok": False,
            "error": str(exc)
        }), 502

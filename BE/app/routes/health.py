from flask import jsonify

from . import bp


@bp.get("/api/health")
def health():
    return jsonify({
        "status": "ok"
    })
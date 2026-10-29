from flask import current_app, jsonify, request

from app.discord_bot import interaction_response, verify_interaction

from . import bp


@bp.post("/api/discord/interactions")
def discord_interactions():
    public_key = current_app.config["DISCORD_PUBLIC_KEY"]
    if not public_key:
        return jsonify({"error": "Discord 봇이 설정되지 않았습니다."}), 503
    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp = request.headers.get("X-Signature-Timestamp", "")
    body = request.get_data(cache=True)
    if not verify_interaction(public_key, signature, timestamp, body):
        return jsonify({"error": "유효하지 않은 Discord 서명입니다."}), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "잘못된 Discord 요청입니다."}), 400
    return jsonify(interaction_response(current_app.config["DATABASE_PATH"], payload))

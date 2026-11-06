import json

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from ..deps import Config
from ..discord_bot import interaction_response, verify_interaction
from ..errors import ApiError

router = APIRouter(tags=["discord"])


@router.post("/api/discord/interactions", summary="Discord Slash Command 수신")
async def discord_interactions(request: Request, config: Config):
    public_key = config["DISCORD_PUBLIC_KEY"]
    if not public_key:
        raise ApiError(503, "Discord 봇이 설정되지 않았습니다.")
    # 서명은 원본 바이트 기준으로 검증해야 하므로 본문을 직접 읽는다.
    body = await request.body()
    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp = request.headers.get("X-Signature-Timestamp", "")
    if not verify_interaction(public_key, signature, timestamp, body):
        raise ApiError(401, "유효하지 않은 Discord 서명입니다.")
    try:
        payload = json.loads(body)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        raise ApiError(400, "잘못된 Discord 요청입니다.")
    return await run_in_threadpool(interaction_response, config["DATABASE_PATH"], payload)

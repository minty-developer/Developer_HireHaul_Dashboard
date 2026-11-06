from fastapi import APIRouter

from ..deps import AdminOnly, Config
from ..errors import ApiError
from ..feed_collector import CollectionError, collect_all, collect_blog
from ..logging_config import logger

router = APIRouter(prefix="/api/admin/sync", tags=["admin"], dependencies=[AdminOnly])


@router.post("", summary="활성 블로그 전체 수집")
def sync_all_blogs(config: Config):
    result = collect_all(
        config["DATABASE_PATH"], discord_bot_token=config["DISCORD_BOT_TOKEN"]
    )
    return {"ok": result["failed"] == 0, **result}


@router.post("/{blog_id}", summary="특정 블로그 수집")
def sync_one_blog(blog_id: int, config: Config):
    try:
        result = collect_blog(
            config["DATABASE_PATH"], blog_id, discord_bot_token=config["DISCORD_BOT_TOKEN"]
        )
    except LookupError as exc:
        raise ApiError(404, str(exc), ok_field=True) from None
    except CollectionError as exc:
        logger.warning("Blog collection failed: %s", exc)
        raise ApiError(502, str(exc), ok_field=True) from None
    return {"ok": True, **result}

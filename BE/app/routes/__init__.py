from fastapi import APIRouter

from . import (
    admin_blogs,
    admin_status,
    admin_sync,
    articles,
    auth,
    blogs,
    discord,
    health,
    home,
    subscriptions,
)

router = APIRouter()
for module in (
    home, health, articles, blogs, auth, subscriptions,
    admin_blogs, admin_sync, admin_status, discord,
):
    router.include_router(module.router)

from fastapi import APIRouter

from . import (
    admin_blogs,
    admin_status,
    articles,
    auth,
    blogs,
    health,
    home,
    subscriptions,
)

router = APIRouter()
for module in (
    home, health, articles, blogs, auth, subscriptions,
    admin_blogs, admin_status,
):
    router.include_router(module.router)

from app.modules.settings.api.admin_router import router as admin_router
from app.modules.settings.api.router import router, shop_router

__all__ = [
    "admin_router",
    "router",
    "shop_router",
]

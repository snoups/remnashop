from app.modules.notifications.api.admin_router import router as admin_router
from app.modules.notifications.api.admin_router import settings_router
from app.modules.notifications.api.public_router import router as public_router

__all__ = ["admin_router", "public_router", "settings_router"]

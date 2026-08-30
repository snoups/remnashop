from app.modules.promocodes.api.admin_router import router as admin_router
from app.modules.promocodes.api.public_router import router as public_router

__all__ = [
    "admin_router",
    "public_router",
]

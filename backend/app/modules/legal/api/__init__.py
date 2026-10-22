from app.modules.legal.api.admin_router import router as admin_router
from app.modules.legal.api.admin_router import user_router
from app.modules.legal.api.cabinet_router import router as cabinet_router
from app.modules.legal.api.router import router

__all__ = [
    "admin_router",
    "cabinet_router",
    "router",
    "user_router",
]

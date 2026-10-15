from app.modules.referrals.api.admin_router import router as admin_router
from app.modules.referrals.api.admin_router import user_router
from app.modules.referrals.api.public_router import router as public_router

__all__ = [
    "admin_router",
    "public_router",
    "user_router",
]

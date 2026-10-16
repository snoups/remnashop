from app.modules.subscriptions.api.admin_router import router as admin_router
from app.modules.subscriptions.api.public_router import own_router
from app.modules.subscriptions.api.public_router import router as public_router
from app.modules.subscriptions.api.router import router

__all__ = ["admin_router", "own_router", "public_router", "router"]

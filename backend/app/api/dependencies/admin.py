from fastapi import Depends, status
from loguru import logger

from app.api.dependencies.public import get_current_actor, require_user_account
from app.api.errors import ApiError
from app.core.actor import Actor
from app.core.error_codes import ErrorCode
from app.modules.users import UserDto


async def require_admin(actor: Actor = Depends(get_current_actor)) -> Actor:
    if not actor.is_privileged:
        logger.warning(f"Non-privileged actor {actor.log} denied admin access")
        raise ApiError(
            status.HTTP_403_FORBIDDEN, "Admin access required", code=ErrorCode.ADMIN_REQUIRED
        )
    return actor


async def require_admin_user(actor: Actor = Depends(require_admin)) -> UserDto:
    """Staff routes acting on the caller's own account (profile, passkeys,
    sessions, notifications); an API token has none."""
    return require_user_account(actor)

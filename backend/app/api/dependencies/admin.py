from fastapi import Depends, Request, status
from loguru import logger

from app.api.dependencies.public import (
    AuthContext,
    forbid_cabinet_proxy,
    get_auth_context,
    require_user_account,
)
from app.api.errors import ApiError
from app.core.actor import Actor
from app.core.enums import SessionAudience
from app.core.error_codes import ErrorCode
from app.modules.users import UserDto


async def require_admin(request: Request, auth: AuthContext = Depends(get_auth_context)) -> Actor:
    forbid_cabinet_proxy(request)
    actor = auth.actor
    if not actor.is_privileged:
        logger.warning(f"Non-privileged actor {actor.log} denied admin access")
        raise ApiError(
            status.HTTP_403_FORBIDDEN, "Admin access required", code=ErrorCode.ADMIN_REQUIRED
        )
    # a cabinet session belongs to the customer UI even for a staff member
    if auth.audience is SessionAudience.CABINET:
        logger.warning(f"Cabinet session of {actor.log} denied admin access")
        raise ApiError(
            status.HTTP_403_FORBIDDEN,
            "Admin access requires a dashboard session",
            code=ErrorCode.SESSION_AUDIENCE_MISMATCH,
        )
    return actor


async def require_admin_user(actor: Actor = Depends(require_admin)) -> UserDto:
    """Staff routes acting on the caller's own account (profile, passkeys,
    sessions, notifications); an API token has none."""
    return require_user_account(actor)

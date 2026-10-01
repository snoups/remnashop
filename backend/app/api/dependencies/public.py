from typing import Optional

import jwt
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from app.api.errors import ApiError
from app.core.actor import Actor, SyntheticActor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.error_codes import ErrorCode
from app.core.security import decode_access_token, hash_refresh_token
from app.core.utils.http import is_ip_allowed, resolve_client_ip
from app.modules.api_tokens import ApiTokenRepository
from app.modules.auth import SessionRepository
from app.modules.users import UserDto, UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def _resolve_api_token_actor(
    credential: str,
    api_token_repository: ApiTokenRepository,
    uow: UnitOfWork,
) -> Optional[SyntheticActor]:
    token = await api_token_repository.get_active_by_hash(hash_refresh_token(credential))
    if token is None:
        return None

    # Unlike interactive sessions (last_used_at only updated on refresh --
    # see SessionRepository.rotate), token traffic is low-volume/scripted,
    # and last_used_at is the operator's main signal for "safe to revoke".
    async with uow:
        await api_token_repository.touch_last_used(token.id)

    return SyntheticActor(
        id=0,  # BaseDto's existing "not persisted" sentinel -- see core/dto.py
        role=Role.USER,
        name=f"API Token: {token.name}",
        is_privileged=True,
        log=f"[api_token:{token.name}]",
        permission_grants=[p.value for p in token.permissions],
    )


@inject
async def get_current_actor(
    request: Request,
    config: FromDishka[AppConfig],
    user_repository: FromDishka[UserRepository],
    session_repository: FromDishka[SessionRepository],
    api_token_repository: FromDishka[ApiTokenRepository],
    uow: FromDishka[UnitOfWork],
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Actor:
    client_ip = resolve_client_ip(request)

    if credentials is None:
        logger.warning(f"Unauthenticated request from IP '{client_ip}'")
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED, "Not authenticated", code=ErrorCode.NOT_AUTHENTICATED
        )

    try:
        payload = decode_access_token(credentials.credentials, config.jwt_secret.get_secret_value())
        user_id = int(payload["sub"])
        session_id = int(payload["sid"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        token_actor = await _resolve_api_token_actor(
            credentials.credentials, api_token_repository, uow
        )
        if token_actor is not None:
            return token_actor
        logger.warning(f"Invalid or expired token from IP '{client_ip}'")
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", code=ErrorCode.TOKEN_INVALID
        ) from None

    session = await session_repository.get_active_by_id(session_id)
    if session is None or session.user_id != user_id:
        logger.warning(f"Token for revoked/expired session_id={session_id} from IP '{client_ip}'")
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", code=ErrorCode.TOKEN_INVALID
        )

    actor = await user_repository.get_by_id(user_id)
    if actor is None:
        logger.warning(f"Token for nonexistent user_id={user_id} from IP '{client_ip}'")
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "User not found", code=ErrorCode.TOKEN_INVALID)

    if actor.is_blocked:
        logger.warning(f"Blocked actor {actor.log} attempted access from IP '{client_ip}'")
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "User is blocked", code=ErrorCode.USER_BLOCKED)

    if actor.ip_allowlist and not is_ip_allowed(client_ip, actor.ip_allowlist):
        logger.warning(f"Actor {actor.log} denied access from disallowed IP '{client_ip}'")
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED,
            "Access denied from this IP address",
            code=ErrorCode.IP_NOT_ALLOWED,
        )

    return actor


async def get_current_user(actor: Actor = Depends(get_current_actor)) -> UserDto:
    """Customer-facing routes: the actor must be a real user row. An API token
    authenticates staff automation and has no customer identity behind it --
    without this it reaches a self-service route as user id 0 and fails on a
    foreign key instead of being refused."""
    if not isinstance(actor, UserDto):
        logger.warning(f"Non-user actor {actor.log} denied access to a customer endpoint")
        raise ApiError(
            status.HTTP_403_FORBIDDEN,
            "This endpoint is available to user accounts only",
            code=ErrorCode.USER_ACCOUNT_REQUIRED,
        )
    return actor

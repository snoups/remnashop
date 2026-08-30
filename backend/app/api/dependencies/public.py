from typing import Optional

import jwt
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.security import decode_access_token, hash_refresh_token
from app.core.utils.http import is_ip_allowed, resolve_client_ip
from app.modules.api_tokens import ApiTokenRepository
from app.modules.auth import SessionRepository
from app.modules.users import UserDto, UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def _resolve_api_token_actor(
    credential: str, api_token_repository: ApiTokenRepository, uow: UnitOfWork
) -> Optional[UserDto]:
    token = await api_token_repository.get_active_by_hash(hash_refresh_token(credential))
    if token is None:
        return None

    # Unlike interactive sessions (last_used_at only updated on refresh --
    # see SessionRepository.rotate), token traffic is low-volume/scripted,
    # and last_used_at is the operator's main signal for "safe to revoke".
    async with uow:
        await api_token_repository.touch_last_used(token.id)

    return UserDto(
        id=0,  # BaseDto's existing "not persisted" sentinel -- see core/dto.py
        role=Role.USER,
        name=f"API Token: {token.name}",
        permission_grants=[p.value for p in token.permissions],
        is_api_token=True,
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
) -> UserDto:
    client_ip = resolve_client_ip(request)

    if credentials is None:
        logger.warning(f"Unauthenticated request from IP '{client_ip}'")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from None

    session = await session_repository.get_active_by_id(session_id)
    if session is None:
        logger.warning(f"Token for revoked/expired session_id={session_id} from IP '{client_ip}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    actor = await user_repository.get_by_id(user_id)
    if actor is None:
        logger.warning(f"Token for nonexistent user_id={user_id} from IP '{client_ip}'")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if actor.is_blocked:
        logger.warning(f"Blocked actor {actor.log} attempted access from IP '{client_ip}'")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is blocked")

    if actor.ip_allowlist and not is_ip_allowed(client_ip, actor.ip_allowlist):
        logger.warning(f"Actor {actor.log} denied access from disallowed IP '{client_ip}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Access denied from this IP address"
        )

    return actor

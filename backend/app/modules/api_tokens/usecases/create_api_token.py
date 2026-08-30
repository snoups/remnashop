from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.security import generate_refresh_token, hash_refresh_token
from app.core.security.permissions import (
    TOKEN_GRANTABLE_PERMISSIONS,
    Permission,
    assert_grantable,
)
from app.core.usecase import UseCase
from app.modules.api_tokens.dto import ApiTokenDto, CreateApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class CreateApiTokenInput:
    name: str
    permissions: list[Permission]
    expires_in_days: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class CreatedApiTokenDto:
    token: ApiTokenDto
    secret: str


class CreateApiTokenUseCase(UseCase[CreateApiTokenInput, CreatedApiTokenDto]):
    required_permission = Permission.API_TOKENS_MANAGE

    def __init__(self, api_token_repository: ApiTokenRepository, uow: UnitOfWork) -> None:
        self._api_token_repository = api_token_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: CreateApiTokenInput) -> CreatedApiTokenDto:
        assert_grantable(data.permissions, allowed=TOKEN_GRANTABLE_PERMISSIONS)

        # Same primitive as refresh tokens/CSRF tokens -- 256 bits of random
        # entropy, unrelated purpose, no reason for separate crypto code.
        secret = generate_refresh_token()

        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)
            if data.expires_in_days is not None
            else None
        )

        async with self._uow:
            token = await self._api_token_repository.create(
                CreateApiTokenDto(
                    name=data.name,
                    permissions=data.permissions,
                    token_hash=hash_refresh_token(secret),
                    created_by_user_id=actor.id if actor.id > 0 else None,
                    expires_at=expires_at,
                )
            )

        return CreatedApiTokenDto(token=token, secret=secret)

from datetime import timedelta

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security import generate_refresh_token, hash_refresh_token
from app.core.security.permissions import Permission, assert_token_scopes
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.api_tokens.dto import (
    CreateApiTokenDto,
    CreatedApiTokenDto,
    IssueApiTokenDto,
)
from app.modules.api_tokens.events import ApiTokenCreatedEvent
from app.modules.api_tokens.repository import ApiTokenRepository


class CreateApiTokenUseCase(UseCase[IssueApiTokenDto, CreatedApiTokenDto]):
    required_permission = Permission.API_TOKENS_MANAGE

    def __init__(
        self,
        api_token_repository: ApiTokenRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._api_token_repository = api_token_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: IssueApiTokenDto) -> CreatedApiTokenDto:
        assert_token_scopes(data.scopes)

        # Same primitive as refresh tokens/CSRF tokens -- 256 bits of random
        # entropy, unrelated purpose, no reason for separate crypto code.
        secret = generate_refresh_token()

        expires_at = datetime_now() + timedelta(days=data.expires_in_days)

        async with self._uow:
            token = await self._api_token_repository.create(
                CreateApiTokenDto(
                    name=data.name,
                    scopes=sorted(set(data.scopes)),
                    token_hash=hash_refresh_token(secret),
                    created_by_user_id=actor.id if actor.id > 0 else None,
                    expires_at=expires_at,
                )
            )
            await self._event_publisher.publish(
                ApiTokenCreatedEvent(user=actor, token_id=token.id, name=token.name)
            )

        return CreatedApiTokenDto(token=token, secret=secret)

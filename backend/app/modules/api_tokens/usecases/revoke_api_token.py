from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.api_tokens.events import ApiTokenRevokedEvent
from app.modules.api_tokens.repository import ApiTokenRepository


class RevokeApiTokenUseCase(UseCase[int, None]):
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

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            revoked = await self._api_token_repository.revoke_by_id(data)
            if revoked is None:
                raise NotFoundError("API token not found", code=ErrorCode.API_TOKEN_NOT_FOUND)
            await self._event_publisher.publish(ApiTokenRevokedEvent(user=actor, token_id=data))

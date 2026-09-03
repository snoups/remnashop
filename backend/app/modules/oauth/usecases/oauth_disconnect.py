from dataclasses import dataclass

from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.oauth.events import OAuthIdentityDisconnectedEvent
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class OAuthDisconnectDto:
    provider: OAuthProvider
    client_ip: str


class OAuthDisconnectUseCase(UseCase[OAuthDisconnectDto, None]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        oauth_identity_repository: OAuthIdentityRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._oauth_identity_repository = oauth_identity_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: OAuthDisconnectDto) -> None:
        async with self._uow:
            deleted = await self._oauth_identity_repository.delete_by_user_and_provider(
                actor.id,
                data.provider,
            )
            if deleted:
                await self._event_publisher.publish(
                    OAuthIdentityDisconnectedEvent(
                        user=actor, provider=data.provider, ip_address=data.client_ip
                    )
                )

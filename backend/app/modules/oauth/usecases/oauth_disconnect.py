from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.auth import SignInMethodGuard
from app.modules.oauth.dto import OAuthDisconnectDto
from app.modules.oauth.events import OAuthIdentityDisconnectedEvent
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.users import UserDto, UserRepository


class OAuthDisconnectUseCase(UseCase[OAuthDisconnectDto, None, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        oauth_identity_repository: OAuthIdentityRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        sign_in_method_guard: SignInMethodGuard,
    ) -> None:
        self._oauth_identity_repository = oauth_identity_repository
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._sign_in_method_guard = sign_in_method_guard

    async def _execute(self, actor: UserDto, data: OAuthDisconnectDto) -> None:
        async with self._uow:
            if data.provider is OAuthProvider.TELEGRAM:
                deleted = actor.telegram_id is not None
                if deleted:
                    await self._user_repository.clear_telegram_id(actor.id)
            else:
                deleted = await self._oauth_identity_repository.delete_by_user_and_provider(
                    actor.id,
                    data.provider,
                )
            if deleted:
                # raising here rolls the removal back
                await self._sign_in_method_guard.assert_one_left(
                    actor, without_provider=data.provider
                )
                await self._event_publisher.publish(
                    OAuthIdentityDisconnectedEvent(
                        user=actor, provider=data.provider, ip_address=data.client_ip
                    )
                )

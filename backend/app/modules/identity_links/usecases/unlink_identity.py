from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher
from app.modules.identity_links.dto import IdentityKind
from app.modules.identity_links.events import SignInMethodUnlinkedEvent
from app.modules.oauth import OAuthIdentityRepository
from app.modules.users import UserDto, UserRepository


class UnlinkIdentityUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        oauth_identity_repository: OAuthIdentityRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._oauth_identity_repository = oauth_identity_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def execute(self, user: UserDto, kind: IdentityKind, client_ip: str) -> None:
        async with self._uow:
            # the row lock serializes concurrent unlinks, so one method always survives
            fresh = await self._user_repository.find_live_for_update(user.id)
            if fresh is None:
                raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
            providers = [
                identity.provider
                for identity in await self._oauth_identity_repository.list_by_user(fresh.id)
            ]
            linked = {
                IdentityKind.TELEGRAM: fresh.telegram_id is not None,
                IdentityKind.EMAIL: fresh.email is not None,
                IdentityKind.GOOGLE: OAuthProvider.GOOGLE in providers,
                IdentityKind.YANDEX: OAuthProvider.YANDEX in providers,
            }
            if not linked[kind]:
                return
            remaining = sum(linked.values())
            if remaining <= 1:
                raise ConflictError(
                    "Can't unlink the last sign-in method", code=ErrorCode.LAST_SIGN_IN_METHOD
                )
            if kind is IdentityKind.TELEGRAM:
                await self._user_repository.clear_telegram_id(fresh.id)
            elif kind is IdentityKind.EMAIL:
                await self._user_repository.set_email(fresh.id, None)
            else:
                await self._oauth_identity_repository.delete_by_user_and_provider(
                    fresh.id, OAuthProvider(kind.value)
                )
            await self._event_publisher.publish(
                SignInMethodUnlinkedEvent(user=fresh, kind=kind, ip_address=client_ip)
            )
        logger.info(f"User {fresh.log} unlinked sign-in method '{kind}'")

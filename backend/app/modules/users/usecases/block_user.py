from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, Role
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.ports import EventPublisher, PasskeyRevoker, SessionRevoker
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import UserDto
from app.modules.users.events import AdminDemotedEvent, UserBlockedEvent
from app.modules.users.repository import UserRepository


class BlockUserUseCase(UseCase[int, UserDto]):
    required_permission = Permission.USERS_BLOCK

    def __init__(
        self,
        user_repository: UserRepository,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        session_revoker: SessionRevoker,
        passkey_revoker: PasskeyRevoker,
    ) -> None:
        self._user_repository = user_repository
        self._blacklist_repository = blacklist_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._session_revoker = session_revoker
        self._passkey_revoker = passkey_revoker

    async def _execute(self, actor: UserDto, user_id: int) -> UserDto:
        async with self._uow:
            target = await self._user_repository.get_by_id(user_id)
            if target is None:
                raise NotFoundError(f"User {user_id} not found")
            # Not a role comparison: an API token authenticates as a synthetic
            # actor with Role.USER, so `actor.role > target.role` refused it every
            # target, including the plain users its own scopes cover. What has to
            # hold is that staff are only ever acted on from above.
            if target.is_privileged and not actor.role > target.role:
                raise PermissionDeniedError
            is_admin = target.role == Role.ADMIN
            # blocking an admin demotes them first -- same gate as demoting directly
            if is_admin and not PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE):
                raise PermissionDeniedError

        async with self._uow:
            if is_admin:
                # same teardown as DemoteAdminUseCase: otherwise unblocking would
                # hand back a working admin login, passkeys and live sessions
                await self._user_repository.demote_from_admin(user_id)
                await self._passkey_revoker.delete_all_by_user(user_id)
                await self._session_revoker.revoke_all_by_user(user_id)
                await self._event_publisher.publish(AdminDemotedEvent(actor=actor, target=target))
            updated = await self._user_repository.set_blocked(user_id, True)
            if updated is None:
                raise NotFoundError(f"User {user_id} not found")
            if target.telegram_id is not None:
                await self._blacklist_repository.add_entry(
                    BlacklistKind.TELEGRAM_ID, str(target.telegram_id)
                )
            if target.email is not None:
                await self._blacklist_repository.add_entry(BlacklistKind.EMAIL, target.email)
            await self._event_publisher.publish(UserBlockedEvent(actor=actor, target=updated))

        return updated

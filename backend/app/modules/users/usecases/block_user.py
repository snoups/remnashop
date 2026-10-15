from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher, PasskeyRevoker, SessionRevoker
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import BlockUserDto, UserDto
from app.modules.users.events import AdminDemotedEvent, UserBlockedEvent
from app.modules.users.repository import UserRepository
from app.modules.users.visibility import assert_manageable, get_visible_target


class BlockUserUseCase(UseCase[BlockUserDto, UserDto]):
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

    async def _execute(self, actor: Actor, data: BlockUserDto) -> UserDto:
        async with self._uow:
            # staff are visible only with ADMINS_MANAGE, the same gate as a demotion
            target = await get_visible_target(
                self._user_repository, actor, data.user_id, for_update=True
            )
            assert_manageable(actor, target)

            if target.role == Role.ADMIN:
                # same teardown as DemoteAdminUseCase: otherwise unblocking would
                # hand back a working admin login, passkeys and live sessions
                await self._user_repository.demote_from_admin(data.user_id)
                await self._passkey_revoker.delete_all_by_user(data.user_id)
                await self._session_revoker.revoke_all_by_user(data.user_id)
                await self._event_publisher.publish(
                    AdminDemotedEvent(actor=actor, target=target, ip_address=data.client_ip)
                )
            updated = await self._user_repository.set_blocked(data.user_id, True)
            if updated is None:
                raise NotFoundError(f"User {data.user_id} not found", code=ErrorCode.USER_NOT_FOUND)
            if target.telegram_id is not None:
                await self._blacklist_repository.add_entry(
                    BlacklistKind.TELEGRAM_ID, str(target.telegram_id)
                )
            if target.email is not None:
                await self._blacklist_repository.add_entry(BlacklistKind.EMAIL, target.email)
            await self._event_publisher.publish(
                UserBlockedEvent(actor=actor, target=updated, ip_address=data.client_ip)
            )

        return updated

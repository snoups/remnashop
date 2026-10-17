from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import DemoteAdminDto, UserDto
from app.modules.users.events import AdminDemotedEvent
from app.modules.users.ports import PasskeyRevoker, SessionRevoker
from app.modules.users.repository import UserRepository


class DemoteAdminUseCase(UseCase[DemoteAdminDto, UserDto]):
    required_permission = Permission.ADMINS_MANAGE

    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        session_revoker: SessionRevoker,
        passkey_revoker: PasskeyRevoker,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._session_revoker = session_revoker
        self._passkey_revoker = passkey_revoker

    async def _execute(self, actor: Actor, data: DemoteAdminDto) -> UserDto:
        async with self._uow:
            target = await self._user_repository.find_live_for_update(data.user_id)
            if target is None:
                raise NotFoundError("Admin not found", code=ErrorCode.ADMIN_NOT_FOUND)
            if target.role != Role.ADMIN:
                raise ConflictError(
                    "Target is not a manageable admin", code=ErrorCode.ADMIN_NOT_MANAGEABLE
                )

            # OAuth identities stay, like telegram_id and email: they're the
            # customer's identity, not admin credentials. Passkeys only open the
            # dashboard and would quietly return access on a later promotion.
            updated = await self._user_repository.demote_from_admin(data.user_id)
            assert updated is not None
            await self._passkey_revoker.delete_all_by_user(data.user_id)
            # demote_from_admin clears login and password, but a live session
            # would keep working as a plain USER, without the dropped
            # ip_allowlist, until it expired
            await self._session_revoker.revoke_all_by_user(data.user_id)
            await self._event_publisher.publish(
                AdminDemotedEvent(actor=actor, target=target, ip_address=data.client_ip)
            )

        return updated

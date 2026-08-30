from dataclasses import dataclass

from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UserDto
from app.modules.users.events import AdminDemotedEvent
from app.modules.users.repository import UserRepository


@dataclass(frozen=True, kw_only=True)
class DemoteAdminDto:
    user_id: int
    client_ip: str


class DemoteAdminUseCase(UseCase[DemoteAdminDto, UserDto]):
    required_permission = Permission.ADMINS_MANAGE

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: DemoteAdminDto) -> UserDto:
        target = await self._user_repository.get_by_id(data.user_id)
        if target is None:
            raise NotFoundError("Admin not found")
        if target.role != Role.ADMIN:
            raise ConflictError("Target is not a manageable admin")

        async with self._uow:
            # OAuth identities (modules/auth) are left untouched -- they're
            # customer-adjacent identity, not admin credentials, same as
            # telegram_id/email surviving demotion.
            updated = await self._user_repository.demote_from_admin(data.user_id)

        assert updated is not None
        await self._event_publisher.publish(
            AdminDemotedEvent(actor=actor, target=target, ip_address=data.client_ip)
        )
        return updated

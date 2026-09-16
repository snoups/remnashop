from dataclasses import dataclass

from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UserDto
from app.modules.users.events import AdminDeletedEvent
from app.modules.users.repository import UserRepository


@dataclass(frozen=True, kw_only=True)
class DeleteAdminDto:
    user_id: int
    client_ip: str


class DeleteAdminUseCase(UseCase[DeleteAdminDto, None]):
    required_permission = Permission.ADMINS_MANAGE

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: DeleteAdminDto) -> None:
        async with self._uow:
            target = await self._user_repository.get_by_id(data.user_id)
            if target is None:
                raise NotFoundError("Admin not found")
            if target.role != Role.ADMIN:
                raise ConflictError("Target is not a manageable admin")
            if target.id == actor.id:
                raise ConflictError("Cannot delete your own account")

        async with self._uow:
            deleted = await self._user_repository.delete(data.user_id)
            if deleted:
                await self._event_publisher.publish(
                    AdminDeletedEvent(actor=actor, target=target, ip_address=data.client_ip)
                )

        if not deleted:
            raise NotFoundError("Admin not found")

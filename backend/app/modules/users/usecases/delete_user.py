from dataclasses import dataclass

from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UserDto
from app.modules.users.events import UserDeletedEvent
from app.modules.users.repository import UserRepository


@dataclass(frozen=True, kw_only=True)
class DeleteUserDto:
    user_id: int
    client_ip: str


class DeleteUserUseCase(UseCase[DeleteUserDto, None]):
    required_permission = Permission.USERS_DELETE

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: DeleteUserDto) -> None:
        target = await self._user_repository.get_by_id(data.user_id)
        if target is None:
            raise NotFoundError("User not found")
        if target.role != Role.USER:
            raise ConflictError("Target is not a deletable user")
        if target.id == actor.id:
            raise ConflictError("Cannot delete your own account")

        async with self._uow:
            deleted = await self._user_repository.delete(data.user_id)

        if not deleted:
            raise NotFoundError("User not found")

        await self._event_publisher.publish(
            UserDeletedEvent(actor=actor, target=target, ip_address=data.client_ip)
        )

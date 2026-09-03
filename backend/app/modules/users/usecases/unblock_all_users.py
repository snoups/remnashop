from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UserDto
from app.modules.users.events import UsersBulkUnblockedEvent
from app.modules.users.repository import UserRepository


class UnblockAllUsersUseCase(UseCase[None, int]):
    required_permission = Permission.USERS_UNBLOCK_ALL

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: None) -> int:
        async with self._uow:
            count = await self._user_repository.unblock_all()
            await self._event_publisher.publish(UsersBulkUnblockedEvent(actor=actor, count=count))

        return count

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.customer_notifications.repository import CustomerNotificationRepository
from app.modules.users import UserDto


class ClearCustomerFeedUseCase(UseCase[None, None, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(self, repository: CustomerNotificationRepository, uow: UnitOfWork) -> None:
        self._repository = repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> None:
        async with self._uow:
            await self._repository.delete_for_user(actor.id)

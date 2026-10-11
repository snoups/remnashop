from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.notifications.repository import NotificationRepository
from app.modules.users import UserDto


class DeletePushSubscriptionUseCase(UseCase[int, None, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, notification_repository: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repository = notification_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        async with self._uow:
            if not await self._notification_repository.delete_push_subscription(data, actor.id):
                raise NotFoundError(
                    f"Push subscription '{data}' not found",
                    code=ErrorCode.PUSH_SUBSCRIPTION_NOT_FOUND,
                )

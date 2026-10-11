from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.notifications.dto import (
    NotificationChannelsDto,
)
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.usecases._channels import to_channels_dto
from app.modules.users import UserDto


class GetNotificationChannelsUseCase(UseCase[None, NotificationChannelsDto, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, notification_repository: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repository = notification_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> NotificationChannelsDto:
        async with self._uow:
            return await to_channels_dto(actor, self._notification_repository)

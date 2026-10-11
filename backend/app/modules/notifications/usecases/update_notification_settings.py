from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.notifications.dto import NotificationSettingsDto, UpdateNotificationSettingsDto
from app.modules.notifications.repository import NotificationRepository


class UpdateNotificationSettingsUseCase(
    UseCase[UpdateNotificationSettingsDto, NotificationSettingsDto]
):
    required_permission = Permission.NOTIFICATION_SETTINGS_MANAGE

    def __init__(self, notification_repository: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repository = notification_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: UpdateNotificationSettingsDto
    ) -> NotificationSettingsDto:
        async with self._uow:
            return await self._notification_repository.update_settings(data)

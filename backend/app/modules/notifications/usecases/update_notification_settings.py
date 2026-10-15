from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.events import changed_fields
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.notifications.dto import NotificationSettingsDto, UpdateNotificationSettingsDto
from app.modules.notifications.events import NotificationSettingsChangedEvent
from app.modules.notifications.repository import NotificationRepository


class UpdateNotificationSettingsUseCase(
    UseCase[UpdateNotificationSettingsDto, NotificationSettingsDto]
):
    required_permission = Permission.NOTIFICATION_SETTINGS_MANAGE

    def __init__(
        self,
        notification_repository: NotificationRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._notification_repository = notification_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(
        self, actor: Actor, data: UpdateNotificationSettingsDto
    ) -> NotificationSettingsDto:
        async with self._uow:
            before = await self._notification_repository.get_settings()
            settings = await self._notification_repository.update_settings(data)
            await self._event_publisher.publish(
                NotificationSettingsChangedEvent(
                    actor=actor, changed_fields=changed_fields(before, settings, vars(data))
                )
            )
        return settings

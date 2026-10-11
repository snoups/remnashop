from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.events import changed_fields
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import EmailSettingsDto, UpdateEmailSettingsDto
from app.modules.settings.events import EmailSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository


class UpdateEmailSettingsUseCase(UseCase[UpdateEmailSettingsDto, EmailSettingsDto]):
    required_permission = Permission.EMAIL_SETTINGS_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdateEmailSettingsDto) -> EmailSettingsDto:
        async with self._uow:
            before = await self._settings_repository.get_email_settings()
            settings = await self._settings_repository.update_email_settings(data)
            await self._event_publisher.publish(
                EmailSettingsChangedEvent(
                    user=actor, changed_fields=changed_fields(before, settings, vars(data))
                )
            )
        logger.info(f"Email settings updated by actor {actor.log}")
        return settings

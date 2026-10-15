from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.events import changed_fields
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import AccessSettingsDto, UpdateAccessSettingsDto
from app.modules.settings.events import AccessSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository


class UpdateAccessSettingsUseCase(UseCase[UpdateAccessSettingsDto, AccessSettingsDto]):
    required_permission = Permission.ACCESS_SETTINGS_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdateAccessSettingsDto) -> AccessSettingsDto:
        async with self._uow:
            before = await self._settings_repository.get_access_settings()
            settings = await self._settings_repository.update_access_settings(data)
            await self._event_publisher.publish(
                AccessSettingsChangedEvent(
                    actor=actor,
                    changed_fields=changed_fields(before, settings, vars(data)),
                    payments_reenabled=not before.payments_enabled and settings.payments_enabled,
                )
            )
        logger.info(f"{actor.log} Updated access settings")
        return settings

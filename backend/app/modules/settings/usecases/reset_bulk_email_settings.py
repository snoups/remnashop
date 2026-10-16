from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.events import changed_fields
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import EmailSettingsDto
from app.modules.settings.events import EmailSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository

_BULK_FIELDS: Final[tuple[str, ...]] = (
    "bulk_host",
    "bulk_port",
    "bulk_security",
    "bulk_username",
    "bulk_password",
    "bulk_from_address",
    "bulk_from_name",
)


class ResetBulkEmailSettingsUseCase(UseCase[None, EmailSettingsDto]):
    required_permission = Permission.EMAIL_SETTINGS_BULK_RESET

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    # the rate limit isn't a connection field and survives a reset
    async def _execute(self, actor: Actor, data: None) -> EmailSettingsDto:
        async with self._uow:
            before = await self._settings_repository.get_email_settings()
            settings = await self._settings_repository.reset_bulk_email_settings()
            await self._event_publisher.publish(
                EmailSettingsChangedEvent(
                    actor=actor, changed_fields=changed_fields(before, settings, _BULK_FIELDS)
                )
            )
        logger.info(f"{actor.log} Reset bulk email settings")
        return settings

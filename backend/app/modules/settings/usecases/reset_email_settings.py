from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.events import changed_fields
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import EmailSettingsDto
from app.modules.settings.events import EmailSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository

_MAIN_FIELDS: Final[tuple[str, ...]] = (
    "host",
    "port",
    "security",
    "username",
    "password",
    "from_address",
    "from_name",
)


class ResetEmailSettingsUseCase(UseCase[None, EmailSettingsDto]):
    required_permission = Permission.EMAIL_SETTINGS_RESET

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
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            # customers signing in by email would lose their only way in without notice
            if cabinet.email_enabled:
                raise ValidationError(
                    "Email sign-in is on and needs this server",
                    code=ErrorCode.EMAIL_SIGN_IN_ENABLED,
                )
            before = await self._settings_repository.get_email_settings()
            settings = await self._settings_repository.reset_email_settings()
            await self._event_publisher.publish(
                EmailSettingsChangedEvent(
                    actor=actor, changed_fields=changed_fields(before, settings, _MAIN_FIELDS)
                )
            )
        logger.info(f"{actor.log} Reset email settings")
        return settings

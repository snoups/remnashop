from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SessionAudience
from app.core.error_codes import ErrorCode
from app.core.events import changed_fields
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import CabinetAuthSettingsDto, UpdateCabinetAuthSettingsDto
from app.modules.settings.events import CabinetAuthSettingsChangedEvent
from app.modules.settings.ports import AudienceSessionRevoker
from app.modules.settings.repository import SettingsRepository


class UpdateCabinetAuthSettingsUseCase(
    UseCase[UpdateCabinetAuthSettingsDto, CabinetAuthSettingsDto]
):
    required_permission = Permission.CABINET_AUTH_SETTINGS_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        session_revoker: AudienceSessionRevoker,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._session_revoker = session_revoker

    async def _execute(
        self, actor: Actor, data: UpdateCabinetAuthSettingsDto
    ) -> CabinetAuthSettingsDto:
        async with self._uow:
            if data.email_enabled:
                email_settings = await self._settings_repository.get_email_settings()
                if not email_settings.is_configured:
                    raise ValidationError(
                        "SMTP is not configured", code=ErrorCode.EMAIL_NOT_CONFIGURED
                    )
            before = await self._settings_repository.get_cabinet_auth_settings()
            settings = await self._settings_repository.update_cabinet_auth_settings(data)
            if settings.captcha_enabled and not settings.is_captcha_configured:
                raise ValidationError(
                    "Captcha keys are not set", code=ErrorCode.CAPTCHA_NOT_CONFIGURED
                )
            # Mini App only now: browser sessions go; the Mini App signs in again with initData
            if before.has_browser_sign_in and not settings.has_browser_sign_in:
                await self._session_revoker.revoke_all_by_audience(SessionAudience.CABINET)
            await self._event_publisher.publish(
                CabinetAuthSettingsChangedEvent(
                    actor=actor, changed_fields=changed_fields(before, settings, vars(data))
                )
            )
        logger.info(f"{actor.log} Updated cabinet sign-in settings")
        return settings

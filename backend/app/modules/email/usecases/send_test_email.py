from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.email.dto import EmailMessageDto, SendTestEmailDto
from app.modules.email.sender import EmailSendError, SmtpSender
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class SendTestEmailUseCase(UseCase[SendTestEmailDto, None, UserDto]):
    required_permission = Permission.EMAIL_SETTINGS_TEST

    def __init__(
        self, settings_repository: SettingsRepository, sender: SmtpSender, uow: UnitOfWork
    ) -> None:
        self._settings_repository = settings_repository
        self._sender = sender
        self._uow = uow

    async def _execute(self, actor: UserDto, data: SendTestEmailDto) -> None:
        async with self._uow:
            settings = await self._settings_repository.get_email_settings()
        if data.bulk and not settings.is_bulk_configured:
            raise ValidationError("SMTP is not configured", code=ErrorCode.EMAIL_NOT_CONFIGURED)
        profile = settings.profile(bulk=data.bulk)
        if not profile.is_configured or profile.from_address is None:
            raise ValidationError("SMTP is not configured", code=ErrorCode.EMAIL_NOT_CONFIGURED)
        message = EmailMessageDto(
            to=actor.email or profile.from_address,
            subject="Test email",
            text="SMTP is configured correctly.",
            html="<p>SMTP is configured correctly.</p>",
        )
        try:
            await self._sender.send(profile, message)
        except EmailSendError as error:
            logger.warning(f"Test email failed: {error}")
            raise ValidationError(
                "Failed to send the email", code=ErrorCode.EMAIL_SEND_FAILED
            ) from error

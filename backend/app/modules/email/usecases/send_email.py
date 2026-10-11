from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.exceptions import RetryableTaskError
from app.core.usecase import UseCase
from app.modules.email.dto import EmailMessageDto
from app.modules.email.sender import EmailSendError, SmtpSender
from app.modules.settings import SettingsRepository


class SendEmailUseCase(UseCase[EmailMessageDto, None]):
    required_permission = None

    def __init__(
        self, settings_repository: SettingsRepository, sender: SmtpSender, uow: UnitOfWork
    ) -> None:
        self._settings_repository = settings_repository
        self._sender = sender
        self._uow = uow

    async def _execute(self, actor: Actor, data: EmailMessageDto) -> None:
        async with self._uow:
            settings = await self._settings_repository.get_email_settings()
        if not settings.is_configured:
            logger.warning("Email not sent: SMTP is not configured")
            return
        try:
            await self._sender.send(settings, data)
        except EmailSendError as error:
            logger.warning(f"Email delivery failed, will retry: {error}")
            raise RetryableTaskError(str(error)) from error

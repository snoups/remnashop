from typing import Final, Optional

from loguru import logger
from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.constants import REDIS_KEY_PREFIX, TIME_1M
from app.core.db.uow import UnitOfWork
from app.core.enums import AppearanceImageKind
from app.core.exceptions import NotFoundError, RetryableTaskError
from app.core.usecase import UseCase
from app.modules.email.dto import EmailMessageDto
from app.modules.email.sender import EmailSendError, SmtpSender
from app.modules.settings import GetPublicAppearanceImageUseCase, SettingsRepository

_PAUSE_KEY: Final[str] = f"{REDIS_KEY_PREFIX}smtp_unavailable"
_PAUSE_SECONDS: Final[int] = TIME_1M


class SendEmailUseCase(UseCase[EmailMessageDto, None]):
    required_permission = None

    def __init__(
        self,
        settings_repository: SettingsRepository,
        sender: SmtpSender,
        redis: Redis,
        get_public_appearance_image: GetPublicAppearanceImageUseCase,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._sender = sender
        self._redis = redis
        self._get_public_appearance_image = get_public_appearance_image
        self._uow = uow

    async def _execute(self, actor: Actor, data: EmailMessageDto) -> None:
        async with self._uow:
            settings = await self._settings_repository.get_email_settings()
        if not settings.is_configured:
            logger.warning("Email not sent: SMTP is not configured")
            return
        if await self._redis.exists(_PAUSE_KEY):
            raise RetryableTaskError("SMTP unavailable")
        logo: Optional[tuple[bytes, str]] = None
        if "cid:logo" in data.html:
            try:
                logo = await self._get_public_appearance_image.execute(AppearanceImageKind.LOGO)
            except NotFoundError:
                pass
        try:
            await self._sender.send(settings, data, logo)
        except EmailSendError as error:
            if error.connection:
                await self._redis.set(_PAUSE_KEY, "1", ex=_PAUSE_SECONDS)
            logger.warning(f"Email delivery failed, will retry: {error}")
            raise RetryableTaskError(str(error)) from error

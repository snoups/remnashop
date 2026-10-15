from loguru import logger

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.render import BroadcastRenderer, load_unsubscribe_labels, outgoing_media
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.telegram_api import (
    SendOutcome,
    TelegramClientFactory,
    send_broadcast_message,
)
from app.modules.broadcasts.validation import promocode_is_usable
from app.modules.promocodes import PromocodeRepository
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationRepository
from app.modules.users import UserDto


class SendTestBroadcastUseCase(UseCase[int, None, UserDto]):
    required_permission = Permission.BROADCASTS_TEST_SEND

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        settings_repository: SettingsRepository,
        promocode_repository: PromocodeRepository,
        translation_repository: TranslationRepository,
        client_factory: TelegramClientFactory,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._settings_repository = settings_repository
        self._promocode_repository = promocode_repository
        self._translation_repository = translation_repository
        self._client_factory = client_factory
        self._config = config
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        if actor.telegram_id is None:
            raise ValidationError("No Telegram linked", code=ErrorCode.BROADCAST_TEST_NO_TELEGRAM)
        async with self._uow:
            broadcast = await self._broadcast_repository.get_by_id(data)
            bot = await self._settings_repository.get_bot_settings()
            contexts = await self._broadcast_repository.recipient_contexts([actor.id])
            code = (
                await promocode_is_usable(self._promocode_repository, broadcast.promocode_id)
                if broadcast.promocode_id is not None
                else None
            )
            labels = await load_unsubscribe_labels(
                self._translation_repository, [actor.language, broadcast.default_locale]
            )
        if bot.token is None:
            raise ValidationError(
                "Bot token is not set", code=ErrorCode.BROADCAST_BOT_NOT_CONFIGURED
            )
        message = BroadcastRenderer(
            broadcast, promocode_code=code, unsubscribe_labels=labels
        ).render(contexts[actor.id], datetime_now())
        media = outgoing_media(self._config.media_dir, broadcast)
        try:
            async with self._client_factory.open(bot.proxy) as client:
                result = await send_broadcast_message(
                    client,
                    bot.token.get_secret_value(),
                    actor.telegram_id,
                    message.text,
                    message.reply_markup,
                    media,
                )
        except FileNotFoundError as error:
            raise ValidationError(
                "Media file is missing", code=ErrorCode.BROADCAST_TEST_FAILED
            ) from error
        if result.outcome is not SendOutcome.SENT:
            raise ValidationError(
                f"Telegram refused: {result.error}", code=ErrorCode.BROADCAST_TEST_FAILED
            )
        logger.info(f"{actor.log} Sent test broadcast '{data}'")

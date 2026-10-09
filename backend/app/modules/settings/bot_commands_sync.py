from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.modules.settings.command_translations import (
    delete_bot_commands_for_locale,
    push_bot_commands_to_telegram,
)
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases.get_bot_commands import GetBotCommandsUseCase
from app.modules.translations import TranslationRepository


class BotCommandsPusher:
    """BotCommandsSync over the Bot API: the command menu is built from the
    stored command order and the active locales' translations."""

    def __init__(
        self,
        settings_repository: SettingsRepository,
        translation_repository: TranslationRepository,
        get_bot_commands: GetBotCommandsUseCase,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._translation_repository = translation_repository
        self._get_bot_commands = get_bot_commands
        self._uow = uow

    async def push(self) -> bool:
        # False when Telegram (or reading what to send) failed; True without a bot
        try:
            async with self._uow:
                bot_settings = await self._settings_repository.get_bot_settings()
            token = bot_settings.token
            if not bot_settings.is_configured or token is None:
                return True
            commands = await self._get_bot_commands.system(False)
            async with self._uow:
                active_locales = await self._translation_repository.list_active_locales()
                translations_by_locale = (
                    await self._translation_repository.get_fluent_text_by_locale(active_locales)
                )
                default_locale = await self._translation_repository.get_default_locale()
        except Exception:
            logger.exception("Failed to prepare bot commands for the Telegram push")
            return False
        return await push_bot_commands_to_telegram(
            token.get_secret_value(),
            bot_settings.proxy,
            [item for item in commands if item.enabled],
            active_locales,
            translations_by_locale,
            default_locale,
        )

    async def drop_locale(self, locale: Locale) -> None:
        async with self._uow:
            bot_settings = await self._settings_repository.get_bot_settings()
        if bot_settings.token is not None:
            await delete_bot_commands_for_locale(
                bot_settings.token.get_secret_value(), bot_settings.proxy, locale
            )

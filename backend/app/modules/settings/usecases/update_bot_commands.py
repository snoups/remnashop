from typing import Optional

from loguru import logger

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.bot_commands import BOT_COMMANDS
from app.modules.settings.command_translations import push_bot_commands_to_telegram
from app.modules.settings.dto import BotCommandDto, UpdateBotCommandsResultDto
from app.modules.settings.repository import SettingsRepository
from app.modules.translations import TranslationsRepository


class UpdateBotCommandsUseCase(UseCase[list[tuple[str, bool]], UpdateBotCommandsResultDto]):
    required_permission = Permission.BOT_COMMANDS_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        translations_repository: TranslationsRepository,
        uow: UnitOfWork,
        config: AppConfig,
    ) -> None:
        self._settings_repository = settings_repository
        self._translations_repository = translations_repository
        self._uow = uow
        self._config = config

    async def _execute(
        self, actor: Actor, data: list[tuple[str, bool]]
    ) -> UpdateBotCommandsResultDto:
        current_names = {item.command for item in BOT_COMMANDS}
        submitted_names = {command for command, _ in data}
        if submitted_names != current_names:
            raise ValidationError(
                f"Commands must match the current set exactly: expected {sorted(current_names)}, "
                f"got {sorted(submitted_names)}",
                code=ErrorCode.BOT_COMMANDS_MISMATCH,
            )

        async with self._uow:
            commands = await self._settings_repository.replace_bot_commands(data)
            bot_settings = await self._settings_repository.get_bot_settings()

        telegram_sync_failed = False
        if bot_settings.is_configured:
            enabled_commands = [item for item in commands if item.enabled]
            token = (
                bot_settings.token.get_secret_value() if bot_settings.token is not None else None
            )
            telegram_sync_failed = not await self._push_to_telegram(token, enabled_commands)

        return UpdateBotCommandsResultDto(
            commands=commands, telegram_sync_failed=telegram_sync_failed
        )

    async def _push_to_telegram(self, token: Optional[str], commands: list[BotCommandDto]) -> bool:
        try:
            async with self._uow:
                active_locales = await self._settings_repository.list_active_locales()
                translations_by_locale = (
                    await self._translations_repository.get_fluent_text_by_locale(active_locales)
                )
            return await push_bot_commands_to_telegram(
                token, commands, active_locales, translations_by_locale, self._config.default_locale
            )
        except Exception:
            # push_bot_commands_to_telegram logs and swallows its own send
            # failures, so anything reaching here is a read/build failure
            # before the first Telegram call.
            logger.exception("Failed to prepare bot commands for the Telegram push")
            return False

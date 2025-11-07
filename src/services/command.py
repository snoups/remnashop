from typing import Optional

from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats
from loguru import logger

from src.core.enums import Command, Locale

from .base import BaseService


class CommandService(BaseService):
    async def setup(self) -> None:
        if not self.config.bot.setup_commands:
            logger.debug(f"Bot commands setup is disabled")
            return

        locales_to_set: list[Optional[Locale]] = list(self.config.locales) + [None]

        for language_code in locales_to_set:
            display_language_code = language_code if language_code else "default"
            i18n = self.translator_hub.get_translator_by_locale(
                locale=language_code or self.config.default_locale
            )

            commands_for_locale = [
                BotCommand(
                    command=cmd_enum.value.command,
                    description=i18n.get(cmd_enum.value.description),
                )
                for cmd_enum in Command
            ]

            success = await self.bot.set_my_commands(
                commands=commands_for_locale,
                scope=BotCommandScopeAllPrivateChats(),
                language_code=language_code,
            )

            if success:
                logger.info(
                    f"Commands successfully set for language '{display_language_code}': "
                    f"{[cmd.command for cmd in commands_for_locale]}"
                )
            else:
                logger.error(f"Failed to set commands for language '{display_language_code}'")

    async def delete(self) -> None:
        if not self.config.bot.setup_commands:
            logger.debug("Bot commands deletion is disabled")
            return

        locales_to_delete: list[Optional[str]] = list(self.config.locales) + [None]

        for language_code in locales_to_delete:
            display_language_code = language_code if language_code else "default"

            success = await self.bot.delete_my_commands(
                scope=BotCommandScopeAllPrivateChats(),
                language_code=language_code,
            )

            if success:
                logger.info(f"Commands deleted for '{display_language_code}'")
            else:
                logger.error(f"Failed to delete commands for '{display_language_code}'")

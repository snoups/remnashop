from typing import Optional

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats
from loguru import logger

from src.application.common import TranslatorHub
from src.core.config import AppConfig
from src.core.enums import Command, Locale


class CommandService:
    def __init__(
        self,
        bot: Bot,
        config: AppConfig,
        translator_hub: TranslatorHub,
    ) -> None:
        self.bot = bot
        self.config = config
        self.translator_hub = translator_hub

    async def setup_commands(self) -> None:
        if not self.config.bot.setup_commands:
            logger.debug("Bot commands setup is disabled")
            await self.delete_commands()
            return

        locales: list[Optional[Locale]] = list(self.config.locales) + [None]

        for lang in locales:
            display_lang = lang if lang else "default"

            i18n = self.translator_hub.get_translator_by_locale(
                locale=lang or self.config.default_locale
            )

            commands = [
                BotCommand(
                    command=cmd.value.command,
                    description=i18n.get(cmd.value.description),
                )
                for cmd in Command
            ]

            success = await self.bot.set_my_commands(
                commands=commands,
                scope=BotCommandScopeAllPrivateChats(),
                language_code=lang,
            )

            if success:
                cmd_list = [c.command for c in commands]
                logger.info(
                    f"Commands successfully set for language '{display_lang}': '{cmd_list}'"
                )
            else:
                logger.error(f"Failed to set commands for language '{display_lang}'")

    async def delete_commands(self) -> None:
        locales: list[Optional[str]] = list(self.config.locales) + [None]

        for lang in locales:
            display_lang = lang if lang else "default"

            success = await self.bot.delete_my_commands(
                scope=BotCommandScopeAllPrivateChats(),
                language_code=lang,
            )

            if success:
                logger.info(f"Commands deleted for language '{display_lang}'")
            else:
                logger.error(f"Failed to delete commands for language '{display_lang}'")

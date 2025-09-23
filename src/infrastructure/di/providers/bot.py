from collections.abc import AsyncIterable

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram_dialog import BgManagerFactory
from dishka import Provider, Scope, from_context, provide

from src.core.config import AppConfig


class BotProvider(Provider):
    scope = Scope.APP

    bg_manager_factory = from_context(provides=BgManagerFactory)

    @provide
    async def get_bot(self, config: AppConfig) -> AsyncIterable[Bot]:
        async with Bot(
            token=config.bot.token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        ) as bot:
            yield bot
        await bot.session.close()

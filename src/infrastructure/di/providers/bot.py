from collections.abc import AsyncIterable

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram_dialog import BgManagerFactory
from aiohttp_socks import ProxyConnector
from dishka import Provider, Scope, from_context, provide
from loguru import logger

from src.core.config import AppConfig


def _build_proxy_connector(url: str) -> ProxyConnector:
    if url.startswith("socks5h://"):
        return ProxyConnector.from_url(url.replace("socks5h://", "socks5://", 1), rdns=True)
    if url.startswith("socks4a://"):
        return ProxyConnector.from_url(url.replace("socks4a://", "socks4://", 1), rdns=True)
    return ProxyConnector.from_url(url)


class BotProvider(Provider):
    scope = Scope.APP

    bg_manager_factory = from_context(provides=BgManagerFactory)

    @provide
    async def get_bot(self, config: AppConfig) -> AsyncIterable[Bot]:
        logger.debug("Initializing Bot instance")

        session = None
        if config.bot.proxy_url:
            proxy = config.bot.proxy_url.get_secret_value()
            logger.info("Using SOCKS5 proxy for Telegram")
            connector = _build_proxy_connector(proxy)
            session = AiohttpSession(connector=connector)

        async with Bot(
            token=config.bot.token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            session=session,
        ) as bot:
            yield bot

        logger.debug("Closing Bot session")
        await bot.session.close()

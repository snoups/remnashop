import asyncio
import sys
from typing import TYPE_CHECKING, Optional

import uvicorn
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from dishka.integrations.aiogram import setup_dishka as setup_aiogram_dishka
from dishka.integrations.fastapi import setup_dishka as setup_fastapi_dishka
from fastapi import FastAPI
from loguru import logger

from app.core.config import AppConfig
from app.core.constants import TELEGRAM_LOGS_KEY
from app.core.logger import add_redis_sink, setup_logger
from app.modules.settings import BotSettingsDto, read_bot_settings
from app.telegram.app import get_app
from app.telegram.container import create_aiogram_container
from app.telegram.dispatcher import get_bg_manager_factory, get_dispatcher, setup_dispatcher
from app.telegram.i18n import read_translator_hub
from app.telegram.idle_app import get_idle_app

if TYPE_CHECKING:
    from fluentogram import TranslatorHub


def build_app(
    config: AppConfig, bot_settings: BotSettingsDto, translator_hub: Optional["TranslatorHub"]
) -> FastAPI:
    if bot_settings.token is None or bot_settings.secret_token is None:
        logger.warning(
            "Bot token not set, telegram service is idle. "
            "Set it in Dashboard -> Settings -> Telegram Bot, then press Restart."
        )
        return get_idle_app(config)

    assert translator_hub is not None  # guaranteed by the __main__ block below
    dispatcher = get_dispatcher(config)
    bg_manager_factory = get_bg_manager_factory(dispatcher)
    proxy = bot_settings.proxy
    bot = Bot(
        token=bot_settings.token.get_secret_value(),
        session=AiohttpSession(proxy=proxy) if proxy is not None else None,
    )

    container = create_aiogram_container(config, bg_manager_factory, bot, translator_hub)
    # Must run before setup_dispatcher(): outer middlewares run in registration
    # order, and UserMiddleware (registered there) reads data[CONTAINER_KEY],
    # which only exists once dishka's own outer middleware has populated it.
    setup_aiogram_dishka(container, dispatcher, auto_inject=True)
    setup_dispatcher(dispatcher)

    app = get_app(
        config,
        dispatcher,
        bot,
        bot_settings.secret_token.get_secret_value(),
        bot_settings.drop_pending_updates,
    )
    setup_fastapi_dishka(container, app)
    return app


if __name__ == "__main__":
    _config = AppConfig.get()
    setup_logger(_config)
    add_redis_sink(_config, TELEGRAM_LOGS_KEY)

    # Startup crashes go through loguru too, so they reach the dashboard log view.
    with logger.catch(onerror=lambda _: sys.exit(1)):
        # Read once, before uvicorn starts its own event loop -- uvicorn calls a
        # `factory=True` app callable synchronously from inside a loop it already
        # owns, so an asyncio.run() in there would fail ("cannot be called from a
        # running event loop"). Fetching the token here, then building a concrete
        # app object, sidesteps that entirely (and matches the "read once at
        # startup, no hot-reload" design -- see /CLAUDE.md).
        _bot_settings = asyncio.run(read_bot_settings(_config))
        # Only read the hub when the bot is actually configured -- an unset
        # token means build_app takes the idle-app path below and never uses
        # it, and read_translator_hub raises when no locale is active yet
        # (exactly the state of a fresh, not-yet-configured deploy).
        _translator_hub = (
            asyncio.run(read_translator_hub(_config))
            if _bot_settings.token is not None and _bot_settings.secret_token is not None
            else None
        )
        _app = build_app(_config, _bot_settings, _translator_hub)

        uvicorn.run(
            app=_app,
            host=_config.bot.host,
            port=_config.bot.port,
            # keep setup_logger's loguru intercept instead of uvicorn's default handlers
            log_config=None,
        )

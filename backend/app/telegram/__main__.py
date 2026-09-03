import asyncio

import uvicorn
from aiogram import Bot
from dishka.integrations.aiogram import setup_dishka as setup_aiogram_dishka
from dishka.integrations.fastapi import setup_dishka as setup_fastapi_dishka
from fastapi import FastAPI
from loguru import logger

from app.core.config import AppConfig
from app.core.logger import setup_logger
from app.modules.settings import BotSettingsDto, read_bot_settings
from app.telegram.app import get_app
from app.telegram.container import create_aiogram_container
from app.telegram.dispatcher import get_bg_manager_factory, get_dispatcher, setup_dispatcher
from app.telegram.idle_app import get_idle_app


def build_app(config: AppConfig, bot_settings: BotSettingsDto) -> FastAPI:
    if bot_settings.token is None or bot_settings.secret_token is None:
        logger.warning(
            "Bot token not set (Dashboard -> Settings -> Bot) -- telegram service idling. "
            "Restart this process after setting it."
        )
        return get_idle_app(config)

    dispatcher = get_dispatcher(config)
    bg_manager_factory = get_bg_manager_factory(dispatcher)
    bot = Bot(token=bot_settings.token.get_secret_value())

    container = create_aiogram_container(config, bg_manager_factory, bot)
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

    # Read once, before uvicorn starts its own event loop -- uvicorn calls a
    # `factory=True` app callable synchronously from inside a loop it already
    # owns, so an asyncio.run() in there would fail ("cannot be called from a
    # running event loop"). Fetching the token here, then building a concrete
    # app object, sidesteps that entirely (and matches the "read once at
    # startup, no hot-reload" design -- see /CLAUDE.md).
    _bot_settings = asyncio.run(read_bot_settings(_config))
    _app = build_app(_config, _bot_settings)

    uvicorn.run(
        app=_app,
        host=_config.bot.host,
        port=_config.bot.port,
    )

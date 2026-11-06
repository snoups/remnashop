from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from dishka.integrations.aiogram import setup_dishka as setup_aiogram_dishka
from dishka.integrations.fastapi import setup_dishka as setup_fastapi_dishka
from fastapi import FastAPI
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.modules.settings import BotSettingsDto
from app.telegram.app import get_app
from app.telegram.container import create_aiogram_container
from app.telegram.dispatcher import get_bg_manager_factory, get_dispatcher, setup_dispatcher


def build_live_app(
    config: AppConfig, bot_settings: BotSettingsDto, translator_hub: TranslatorHub
) -> FastAPI:
    # imported only once a bot token is set, so an idle telegram process
    # never loads aiogram and the bot's dependency graph
    assert bot_settings.token is not None and bot_settings.secret_token is not None
    dispatcher = get_dispatcher(config)
    bg_manager_factory = get_bg_manager_factory(dispatcher)
    bot = Bot(
        token=bot_settings.token.get_secret_value(),
        session=AiohttpSession(
            proxy=bot_settings.proxy, api=TelegramAPIServer.from_base(config.bot.api_url)
        ),
    )

    container = create_aiogram_container(config, bg_manager_factory, bot, translator_hub)
    # Must run before setup_dispatcher(): outer middlewares run in registration
    # order, and UserMiddleware (registered there) reads data[CONTAINER_KEY],
    # which only exists once dishka's outer middleware has populated it.
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

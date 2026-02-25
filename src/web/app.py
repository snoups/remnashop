from aiogram import Dispatcher
from fastapi import FastAPI
from loguru import logger
from starlette.middleware.cors import CORSMiddleware

from src.core.config import AppConfig
from src.lifespan import lifespan

from .endpoints import TelegramWebhookEndpoint, payments_router, remnawave_router


def get_app(config: AppConfig, dispatcher: Dispatcher) -> FastAPI:
    app: FastAPI = FastAPI(
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        include_in_schema=False,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(payments_router)
    app.include_router(remnawave_router)

    telegram_webhook_endpoint = TelegramWebhookEndpoint(
        dispatcher=dispatcher,
        secret_token=config.bot.secret_token.get_secret_value(),
    )

    telegram_webhook_endpoint.register(app=app, path=config.bot.webhook_path)

    app.state.telegram_webhook_endpoint = telegram_webhook_endpoint
    app.state.dispatcher = dispatcher

    logger.info("FastAPI application initialized'")
    return app

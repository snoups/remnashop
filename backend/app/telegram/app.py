from aiogram import Bot, Dispatcher
from fastapi import FastAPI
from loguru import logger

from app.core.config import AppConfig
from app.telegram.lifespan import lifespan
from app.telegram.webhook import TelegramWebhookEndpoint


def get_app(
    config: AppConfig,
    dispatcher: Dispatcher,
    bot: Bot,
    secret_token: str,
    drop_pending_updates: bool,
) -> FastAPI:
    app: FastAPI = FastAPI(
        lifespan=lifespan,
        title="Remnashop Telegram Webhook",
        version=config.build.version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    endpoint = TelegramWebhookEndpoint(dispatcher=dispatcher, secret_token=secret_token)
    endpoint.register(app=app, path=config.bot.webhook_path)

    app.state.telegram_webhook_endpoint = endpoint
    app.state.bot = bot
    app.state.drop_pending_updates = drop_pending_updates

    logger.info("Telegram webhook FastAPI application initialized")
    return app

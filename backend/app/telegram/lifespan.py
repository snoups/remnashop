import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from aiogram import Bot
from aiogram.methods import SetWebhook
from dishka import AsyncContainer, Scope
from fastapi import FastAPI
from loguru import logger

from app.core.config import AppConfig
from app.telegram.restart_listener import listen_for_restart
from app.telegram.webhook import TelegramWebhookEndpoint


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    container: AsyncContainer = app.state.dishka_container
    bot: Bot = app.state.bot
    endpoint: TelegramWebhookEndpoint = app.state.telegram_webhook_endpoint

    async with container(scope=Scope.REQUEST) as startup_container:
        config = await startup_container.get(AppConfig)

        webhook_url = config.bot.webhook_url(config.domain).get_secret_value()
        await bot(
            SetWebhook(
                url=webhook_url,
                secret_token=endpoint.secret_token,
                drop_pending_updates=app.state.drop_pending_updates,
            )
        )
        logger.info(f"Webhook set to '{webhook_url}'")

    restart_task = asyncio.create_task(listen_for_restart(config))

    await endpoint.startup()

    yield

    restart_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await restart_task
    await endpoint.shutdown()
    await container.close()

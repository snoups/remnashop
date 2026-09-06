import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from aiogram import Bot
from aiogram.methods import SetWebhook
from dishka import AsyncContainer, Scope
from fastapi import FastAPI
from fluentogram import TranslatorHub
from loguru import logger

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.modules.dialogs import DialogRepository, ensure_dialogs_seeded
from app.modules.settings import SettingsRepository
from app.modules.translations import TranslationsRepository
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.config_listener import listen_for_dialog_config_changes
from app.telegram.restart_listener import listen_for_restart
from app.telegram.translation_listener import listen_for_translation_changes
from app.telegram.webhook import TelegramWebhookEndpoint


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    container: AsyncContainer = app.state.dishka_container
    bot: Bot = app.state.bot
    endpoint: TelegramWebhookEndpoint = app.state.telegram_webhook_endpoint

    async with container(scope=Scope.REQUEST) as startup_container:
        config = await startup_container.get(AppConfig)
        dialog_repository = await startup_container.get(DialogRepository)
        translations_repository = await startup_container.get(TranslationsRepository)
        settings_repository = await startup_container.get(SettingsRepository)
        uow = await startup_container.get(UnitOfWork)
        async with uow:
            await ensure_dialogs_seeded(
                dialog_repository, translations_repository, settings_repository
            )

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

    dialog_cache = await container.get(DialogConfigCache)
    dialog_config_task = asyncio.create_task(listen_for_dialog_config_changes(config, dialog_cache))

    translator_hub = await container.get(TranslatorHub)
    translation_task = asyncio.create_task(listen_for_translation_changes(config, translator_hub))

    await endpoint.startup()

    yield

    dialog_config_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await dialog_config_task
    translation_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await translation_task
    restart_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await restart_task
    await endpoint.shutdown()
    await container.close()

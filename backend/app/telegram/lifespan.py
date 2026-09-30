import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Final, Optional

from aiogram import Bot
from aiogram.methods import GetWebhookInfo, SetWebhook
from dishka import AsyncContainer, Scope
from fastapi import FastAPI
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.runtime_heartbeat import poll_runtime_heartbeat
from app.modules.dialogs import DialogRepository, ensure_dialogs_seeded
from app.modules.settings import SettingsRepository, repush_bot_commands_if_configured
from app.modules.translations import TranslationsRepository
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.config_listener import listen_for_dialog_config_changes
from app.telegram.restart_listener import listen_for_restart
from app.telegram.translation_listener import listen_for_translation_changes
from app.telegram.webhook import TelegramWebhookEndpoint

_BOT_STATE_LABELS: Final[dict[Optional[bool], str]] = {
    True: "Enabled",
    False: "Disabled",
    None: "Unknown",
}


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
        await repush_bot_commands_if_configured(
            settings_repository, translations_repository, config, uow
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

        webhook_info = await bot(GetWebhookInfo())
        if webhook_info.last_error_message:
            logger.critical(
                f"Webhook has a last error message: '{webhook_info.last_error_message}'"
            )

        me = await bot.get_me()
        if not me.supports_inline_queries:
            logger.warning(
                "Bot is not enabled for inline mode. "
                "Please enable Inline Mode in BotFather for correct work of some features"
            )

    restart_task = asyncio.create_task(listen_for_restart(config))

    dialog_cache = await container.get(DialogConfigCache)
    dialog_config_task = asyncio.create_task(listen_for_dialog_config_changes(config, dialog_cache))

    translator_hub = await container.get(TranslatorHub)
    translation_task = asyncio.create_task(listen_for_translation_changes(config, translator_hub))

    redis = await container.get(Redis)
    runtime_heartbeat_task = asyncio.create_task(poll_runtime_heartbeat(redis, "telegram"))

    await endpoint.startup()

    build = config.build
    reads_all = me.can_read_all_group_messages
    privacy_mode = None if reads_all is None else not reads_all
    logger.opt(colors=True).info(
        rf"""
    <cyan> _____                                _                 </>
    <cyan>|  __ \                              | |                </>
    <cyan>| |__) |___ _ __ ___  _ __   __ _ ___| |__   ___  _ __  </>
    <cyan>|  _  // _ \ '_ ` _ \| '_ \ / _` / __| '_ \ / _ \| '_ \ </>
    <cyan>| | \ \  __/ | | | | | | | | (_| \__ \ | | | (_) | |_) |</>
    <cyan>|_|  \_\___|_| |_| |_|_| |_|\__,_|___/_| |_|\___/| .__/ </>
    <cyan>                                                 | |    </>
    <cyan>                                                 |_|    </>

        <green>Build Time: {build.time}</>
        <green>Branch: {build.branch} ({build.tag})</>
        <green>Commit: {build.commit}</>
        <cyan>------------------------</>
        Bot          - @{me.username}
        Groups Mode  - {_BOT_STATE_LABELS[me.can_join_groups]}
        Privacy Mode - {_BOT_STATE_LABELS[privacy_mode]}
        Inline Mode  - {_BOT_STATE_LABELS[me.supports_inline_queries]}
        """  # noqa: W605
    )

    yield

    runtime_heartbeat_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await runtime_heartbeat_task
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

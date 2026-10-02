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
from app.core.ports import BotCommandsSync
from app.core.runtime_heartbeat import poll_runtime_heartbeat
from app.modules.dialogs import DialogRepository, ensure_dialogs_seeded
from app.modules.translations import TranslationRepository
from app.telegram.bot_signals import listen_for_bot_signals, live_update_handlers
from app.telegram.dialogs.config_cache import DialogConfigCache
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
        translation_repository = await startup_container.get(TranslationRepository)
        uow = await startup_container.get(UnitOfWork)
        async with uow:
            await ensure_dialogs_seeded(dialog_repository, translation_repository)
        await (await startup_container.get(BotCommandsSync)).push()

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

    redis = await container.get(Redis)
    handlers = live_update_handlers(
        await container.get(DialogConfigCache), await container.get(TranslatorHub)
    )
    bot_signals_task = asyncio.create_task(listen_for_bot_signals(redis, handlers))
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
        """
    )

    yield

    runtime_heartbeat_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await runtime_heartbeat_task
    bot_signals_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await bot_signals_task
    await endpoint.shutdown()
    await container.close()

import asyncio
import contextlib
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncGenerator, Final, Optional

from aiogram import Bot
from aiogram.methods import GetWebhookInfo, SetWebhook
from aiogram.types import WebhookInfo
from aiogram_dialog import BgManagerFactory
from dishka import AsyncContainer, Scope
from fastapi import FastAPI
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.db.startup_lock import lock_startup_seeding
from app.core.db.uow import UnitOfWork
from app.core.runtime_heartbeat import poll_runtime_heartbeat
from app.core.utils.time import datetime_now
from app.modules.dialogs import DialogRepository, ensure_dialogs_seeded
from app.modules.settings import BotStatusKind, ReportBotStatusDto, ReportBotStatusUseCase
from app.modules.translations import BotCommandsSync, TranslationRepository
from app.telegram.bot_signals import live_update_handlers, payment_outcome_handlers
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.signal_listener import listen_for_bot_signals
from app.telegram.webhook import TelegramWebhookEndpoint

# Telegram keeps the last error indefinitely; only one this recent is news on startup
_WEBHOOK_ERROR_MAX_AGE: Final[timedelta] = timedelta(minutes=10)
_BOT_STATE_LABELS: Final[dict[Optional[bool], str]] = {
    True: "Enabled",
    False: "Disabled",
    None: "Unknown",
}


def is_fresh_webhook_error(info: WebhookInfo, now: datetime) -> bool:
    if not info.last_error_message or info.last_error_date is None:
        return False
    return now - info.last_error_date < _WEBHOOK_ERROR_MAX_AGE


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    container: AsyncContainer = app.state.dishka_container
    bot: Bot = app.state.bot
    endpoint: TelegramWebhookEndpoint = app.state.telegram_webhook_endpoint
    started_at = time.monotonic()

    async with container(scope=Scope.REQUEST) as startup_container:
        config = await startup_container.get(AppConfig)
        dialog_repository = await startup_container.get(DialogRepository)
        translation_repository = await startup_container.get(TranslationRepository)
        uow = await startup_container.get(UnitOfWork)
        async with uow:
            await lock_startup_seeding(await startup_container.get(AsyncSession))
            await ensure_dialogs_seeded(dialog_repository, translation_repository)
        await (await startup_container.get(BotCommandsSync)).push()

        report_status = await startup_container.get(ReportBotStatusUseCase)
        webhook_url = config.bot.webhook_url(config.domain).get_secret_value()
        try:
            await bot(
                SetWebhook(
                    url=webhook_url,
                    secret_token=endpoint.secret_token,
                    drop_pending_updates=app.state.drop_pending_updates,
                    # chat_member is off unless asked for, and the channel guard needs it
                    allowed_updates=endpoint.dispatcher.resolve_used_update_types(),
                )
            )
        except Exception as error:
            await report_status.system(
                ReportBotStatusDto(kind=BotStatusKind.WEBHOOK_FAILED, detail=str(error))
            )
            raise
        logger.info(f"Webhook set to '{webhook_url}'")

        webhook_info = await bot(GetWebhookInfo())
        if webhook_info.last_error_message:
            logger.critical(
                f"Webhook has a last error message: '{webhook_info.last_error_message}'"
            )
        if is_fresh_webhook_error(webhook_info, datetime_now()):
            await report_status.system(
                ReportBotStatusDto(
                    kind=BotStatusKind.WEBHOOK_FAILED, detail=webhook_info.last_error_message
                )
            )

        me = await bot.get_me()
        await report_status.system(
            ReportBotStatusDto(kind=BotStatusKind.STARTED, detail=me.username)
        )

    redis = await container.get(Redis)
    handlers = {
        **live_update_handlers(
            await container.get(DialogConfigCache), await container.get(TranslatorHub)
        ),
        **payment_outcome_handlers(app.state.bot, await container.get(BgManagerFactory)),
    }
    bot_signals_task = asyncio.create_task(listen_for_bot_signals(redis, handlers))
    runtime_heartbeat_task = asyncio.create_task(
        poll_runtime_heartbeat(redis, "telegram", config.instance_name)
    )

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

    # a lost event must not keep the background tasks below running
    try:
        async with container(scope=Scope.REQUEST) as shutdown_container:
            await (await shutdown_container.get(ReportBotStatusUseCase)).system(
                ReportBotStatusDto(
                    kind=BotStatusKind.STOPPED,
                    uptime_seconds=int(time.monotonic() - started_at),
                )
            )
    except Exception:
        logger.exception("Failed to report the bot stop")
    runtime_heartbeat_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await runtime_heartbeat_task
    bot_signals_task.cancel()
    # a listener that died on its own must not stop the shutdown below
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await bot_signals_task
    await endpoint.shutdown()
    await container.close()

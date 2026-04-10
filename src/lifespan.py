import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from aiogram import Dispatcher
from aiogram.types import WebhookInfo
from dishka import AsyncContainer, Scope
from fastapi import FastAPI
from loguru import logger

from src.application.common import Remnawave
from src.application.common.dao import SettingsDao
from src.application.events import (
    BotShutdownEvent,
    BotStartupEvent,
    RemnawaveErrorEvent,
    RemnawaveVersionWarningEvent,
    WebhookErrorEvent,
)
from src.application.events.system import RemnashopWelcomeEvent
from src.application.services import BotService, CommandService, WebhookService
from src.application.use_cases.gateways.commands.payment import CreateDefaultPaymentGateway
from src.core.config import AppConfig
from src.core.constants import REMNAWAVE_MAX_VERSION
from src.core.utils.i18n_helpers import i18n_format_seconds
from src.core.utils.time import get_uptime
from src.infrastructure.services import EventBusImpl
from src.web.endpoints import TelegramWebhookEndpoint


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    dispatcher: Dispatcher = app.state.dispatcher
    telegram_webhook_endpoint: TelegramWebhookEndpoint = app.state.telegram_webhook_endpoint
    container: AsyncContainer = app.state.dishka_container

    event_bus = await container.get(EventBusImpl)
    event_bus.set_container_factory(lambda: container)
    event_bus.autodiscover()

    async with container(scope=Scope.REQUEST) as startup_container:
        config = await startup_container.get(AppConfig)
        bot_service = await startup_container.get(BotService)
        settings_dao = await startup_container.get(SettingsDao)
        webhook_service = await startup_container.get(WebhookService)
        command_service = await startup_container.get(CommandService)
        remnawave_service = await startup_container.get(Remnawave)
        create_default_payment_gateway = await startup_container.get(CreateDefaultPaymentGateway)

        if not await bot_service.is_inline_enabled():
            logger.warning(
                "Bot is not enabled for inline mode. "
                "Please enable Inline Mode in BotFather for correct work of some features"
            )

        states = await bot_service.get_bot_states()
        await create_default_payment_gateway.system()
        settings = await settings_dao.get()
        allowed_updates = dispatcher.resolve_used_update_types()
        webhook_info: WebhookInfo = await webhook_service.setup_webhook(allowed_updates)

        if webhook_service.has_error(webhook_info):
            logger.critical(
                f"Webhook has a last error message: '{webhook_info.last_error_message}'"
            )
            webhook_error_event = WebhookErrorEvent()
            await event_bus.publish(webhook_error_event)

        await command_service.setup_commands()

    await telegram_webhook_endpoint.startup()

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

        <green>Build Time: {config.build.time}</>
        <green>Branch: {config.build.branch} ({config.build.tag})</>
        <green>Commit: {config.build.commit}</>
        <cyan>------------------------</>
        Groups Mode  - {states["groups_mode"]}"
        Privacy Mode - {states["privacy_mode"]}"
        Inline Mode  - {states["inline_mode"]}"
        <cyan>------------------------</>
        <yellow>Bot in access mode: '{settings.access.mode}'</>
        <yellow>Payments allowed: '{settings.access.payments_allowed}'</>
        <yellow>Registration allowed: '{settings.access.registration_allowed}'</>
        """  # noqa: W605
    )

    await event_bus.publish(RemnashopWelcomeEvent())

    bot_startup_event = BotStartupEvent(
        **config.build.data,
        access_mode=settings.access.mode,
        payments_allowed=settings.access.payments_allowed,
        registration_allowed=settings.access.registration_allowed,
    )
    await event_bus.publish(bot_startup_event)

    try:
        panel_version = await remnawave_service.try_connection()
        if panel_version >= REMNAWAVE_MAX_VERSION:
            await event_bus.publish(
                RemnawaveVersionWarningEvent(
                    **config.build.data,
                    panel_version=str(panel_version),
                )
            )
    except Exception as e:
        remnawave_error_event = RemnawaveErrorEvent(**config.build.data, exception=e)
        await event_bus.publish(remnawave_error_event)

    yield

    bot_shutdown_event = BotShutdownEvent(
        **config.build.data,
        uptime=i18n_format_seconds(get_uptime()),
    )
    await event_bus.publish(bot_shutdown_event)

    await asyncio.sleep(2)

    await event_bus.shutdown()
    await telegram_webhook_endpoint.shutdown()
    await command_service.delete_commands()
    await webhook_service.delete_webhook()
    await container.close()

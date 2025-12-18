import asyncio
import traceback
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from aiogram import Bot, Dispatcher
from aiogram.types import WebhookInfo
from aiogram.utils.formatting import Text
from dishka import AsyncContainer, Scope
from fastapi import FastAPI
from loguru import logger

from src.__version__ import __version__
from src.api.endpoints import TelegramWebhookEndpoint
from src.core.config.app import AppConfig
from src.core.enums import SystemNotificationType
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.taskiq.tasks.updates import check_bot_update
from src.services.command import CommandService
from src.services.notification import NotificationService
from src.services.payment_gateway import PaymentGatewayService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.webhook import WebhookService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    dispatcher: Dispatcher = app.state.dispatcher
    telegram_webhook_endpoint: TelegramWebhookEndpoint = app.state.telegram_webhook_endpoint
    container: AsyncContainer = app.state.dishka_container

    async with container(scope=Scope.REQUEST) as startup_container:
        config: AppConfig = await startup_container.get(AppConfig)
        webhook_service: WebhookService = await startup_container.get(WebhookService)
        command_service: CommandService = await startup_container.get(CommandService)
        settings_service: SettingsService = await startup_container.get(SettingsService)
        gateway_service: PaymentGatewayService = await startup_container.get(PaymentGatewayService)
        remnawave_service: RemnawaveService = await startup_container.get(RemnawaveService)
        notification_service: NotificationService = await startup_container.get(NotificationService)

        await gateway_service.create_default()
        settings = await settings_service.get()

    await startup_container.close()

    allowed_updates = dispatcher.resolve_used_update_types()
    webhook_info: WebhookInfo = await webhook_service.setup(allowed_updates)

    if webhook_service.has_error(webhook_info):
        logger.critical(f"Webhook has a last error message: '{webhook_info.last_error_message}'")
        await notification_service.system_notify(
            ntf_type=SystemNotificationType.BOT_LIFETIME,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-error-webhook",
                i18n_kwargs={"error": webhook_info.last_error_message},
            ),
        )

    await command_service.setup()
    await telegram_webhook_endpoint.startup()

    bot: Bot = await container.get(Bot)
    bot_info = await bot.get_me()
    states: dict[Optional[bool], str] = {True: "Enabled", False: "Disabled", None: "Unknown"}

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

        <green>Version: {__version__}</>
        <green>Build Time: {config.build.time}</>
        <green>Branch: {config.build.branch} ({config.build.tag})</>
        <green>Commit: {config.build.commit}</>
        <cyan>------------------------</>
        Groups Mode  - {states[bot_info.can_join_groups]}
        Privacy Mode - {states[not bot_info.can_read_all_group_messages]}
        Inline Mode  - {states[bot_info.supports_inline_queries]}
        <cyan>------------------------</>
        <yellow>Bot in access mode: '{settings.access_mode}'</>
        <yellow>Purchases allowed: '{settings.purchases_allowed}'</>
        <yellow>Registration allowed: '{settings.registration_allowed}'</>
        """  # noqa: W605
    )
    await check_bot_update.kiq()
    await notification_service.remnashop_notify()
    await asyncio.sleep(2)
    await notification_service.system_notify(
        ntf_type=SystemNotificationType.BOT_LIFETIME,
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-event-bot-startup",
            i18n_kwargs={
                "access_mode": settings.access_mode,
                "purchases_allowed": settings.purchases_allowed,
                "registration_allowed": settings.registration_allowed,
            },
        ),
    )

    try:
        await remnawave_service.try_connection()
    except Exception as exception:
        logger.exception(f"Remnawave connection failed: {exception}")
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        await notification_service.error_notify(
            traceback_str=traceback.format_exc(),
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-error-remnawave",
                i18n_kwargs={
                    "error": f"{error_type_name}: {error_message.as_html()}",
                },
            ),
        )

    yield

    await notification_service.system_notify(
        ntf_type=SystemNotificationType.BOT_LIFETIME,
        payload=MessagePayload.not_deleted(i18n_key="ntf-event-bot-shutdown"),
    )

    await telegram_webhook_endpoint.shutdown()
    await command_service.delete()
    await webhook_service.delete()

    await container.close()

from typing import Any

from aiogram.types import BufferedInputFile
from dishka import FromDishka
from dishka.integrations.taskiq import inject

from src.core.enums import MediaType, SystemNotificationType
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.taskiq.broker import broker
from src.services.notification import NotificationService


@broker.task
@inject
async def send_system_notification_task(
    ntf_type: SystemNotificationType,
    i18n_key: str,
    notification_service: FromDishka[NotificationService],
    i18n_kwargs: dict[str, Any] = {},
) -> None:
    await notification_service.system_notify(
        payload=MessagePayload(
            i18n_key=i18n_key,
            i18n_kwargs=i18n_kwargs,
            auto_delete_after=None,
            add_close_button=True,
        ),
        ntf_type=ntf_type,
    )


@broker.task
@inject
async def send_remnashop_notification_task(
    notification_service: FromDishka[NotificationService],
) -> None:
    await notification_service.remnashop_notify()


@broker.task
@inject
async def send_error_notification_task(
    update_id: int,
    traceback_str: str,
    i18n_kwargs: dict[str, Any],
    notification_service: FromDishka[NotificationService],
) -> None:
    file_data = BufferedInputFile(
        file=traceback_str.encode(),
        filename=f"error_{update_id}.txt",
    )

    await notification_service.notify_super_dev(
        payload=MessagePayload(
            i18n_key="ntf-event-error",
            i18n_kwargs=i18n_kwargs,
            media=file_data,
            media_type=MediaType.DOCUMENT,
            auto_delete_after=None,
            add_close_button=True,
        ),
    )

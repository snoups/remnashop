import asyncio
from typing import Any, Union, cast

from aiogram.types import BufferedInputFile
from dishka.integrations.taskiq import FromDishka, inject

from src.bot.keyboards import get_renew_keyboard
from src.core.constants import BATCH_DELAY, BATCH_SIZE
from src.core.enums import MediaType, SystemNotificationType, UserNotificationType
from src.core.utils.iterables import chunked
from src.core.utils.message_payload import MessagePayload
from src.core.utils.types import RemnaUserDto
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.taskiq.broker import broker
from src.services.notification import NotificationService
from src.services.user import UserService


@broker.task
@inject
async def send_system_notification_task(
    ntf_type: SystemNotificationType,
    payload: MessagePayload,
    notification_service: FromDishka[NotificationService],
) -> None:
    await notification_service.system_notify(payload=payload, ntf_type=ntf_type)


@broker.task
@inject
async def send_remnashop_notification_task(
    notification_service: FromDishka[NotificationService],
) -> None:
    await notification_service.remnashop_notify()


@broker.task
@inject
async def send_error_notification_task(
    error_id: Union[str, int],
    traceback_str: str,
    i18n_kwargs: dict[str, Any],
    notification_service: FromDishka[NotificationService],
    i18n_key: str = "ntf-event-error",
) -> None:
    file_data = BufferedInputFile(
        file=traceback_str.encode(),
        filename=f"error_{error_id}.txt",
    )

    await notification_service.notify_super_dev(
        payload=MessagePayload(
            i18n_key=i18n_key,
            i18n_kwargs=i18n_kwargs,
            media=file_data,
            media_type=MediaType.DOCUMENT,
            auto_delete_after=None,
            add_close_button=True,
        ),
    )


@broker.task
@inject
async def send_access_denied_notification_task(
    user: UserDto,
    i18n_key: str,
    notification_service: FromDishka[NotificationService],
) -> None:
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key=i18n_key),
    )


@broker.task
@inject
async def send_access_opened_notifications_task(
    waiting_user_ids: list[int],
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    for batch in chunked(waiting_user_ids, BATCH_SIZE):
        for user_telegram_id in batch:
            user = await user_service.get(user_telegram_id)
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(
                    i18n_key="ntf-access-allowed",
                    auto_delete_after=None,
                    add_close_button=True,
                ),
            )
        await asyncio.sleep(BATCH_DELAY)


@broker.task
@inject
async def send_subscription_expire_notification_task(
    remna_user: RemnaUserDto,
    ntf_type: UserNotificationType,
    i18n_kwargs: dict[str, Any],
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    telegram_id = cast(int, remna_user.telegram_id)

    if ntf_type == UserNotificationType.EXPIRES_IN_3_DAYS:
        i18n_key = "ntf-event-user-expiring"
        i18n_kwargs_extra = {"value": 3}
    elif ntf_type == UserNotificationType.EXPIRES_IN_2_DAYS:
        i18n_key = "ntf-event-user-expiring"
        i18n_kwargs_extra = {"value": 2}
    elif ntf_type == UserNotificationType.EXPIRES_IN_1_DAYS:
        i18n_key = "ntf-event-user-expiring"
        i18n_kwargs_extra = {"value": 1}
    elif ntf_type == UserNotificationType.EXPIRED:
        i18n_key = "ntf-event-user-expired"
        i18n_kwargs_extra = {}

    user = await user_service.get(telegram_id)

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key=i18n_key,
            i18n_kwargs={**i18n_kwargs, **i18n_kwargs_extra},
            reply_markup=get_renew_keyboard(),
            auto_delete_after=None,
            add_close_button=True,
        ),
        ntf_type=ntf_type,
    )


@broker.task
@inject
async def send_subscription_limited_notification_task(
    remna_user: RemnaUserDto,
    i18n_kwargs: dict[str, Any],
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    telegram_id = cast(int, remna_user.telegram_id)
    user = await user_service.get(telegram_id)

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-event-user-limited",
            i18n_kwargs=i18n_kwargs,
            reply_markup=get_renew_keyboard(),
            auto_delete_after=None,
            add_close_button=True,
        ),
        ntf_type=UserNotificationType.LIMITED,
    )


@broker.task
@inject
async def send_test_transaction_notification_task(
    user: UserDto,
    notification_service: FromDishka[NotificationService],
) -> None:
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-gateway-test-payment-confirmed",
        ),
    )

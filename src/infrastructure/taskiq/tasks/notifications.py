import asyncio
from typing import Any, Union, cast

from aiogram.types import BufferedInputFile
from dishka.integrations.taskiq import FromDishka, inject

from src.bot.keyboards import get_buy_keyboard, get_renew_keyboard
from src.core.constants import BATCH_DELAY, BATCH_SIZE
from src.core.enums import MediaType, UserNotificationType
from src.core.utils.iterables import chunked
from src.core.utils.message_payload import MessagePayload
from src.core.utils.types import RemnaUserDto
from src.infrastructure.taskiq.broker import broker
from src.services.notification import NotificationService
from src.services.user import UserService


@broker.task
@inject
async def send_error_notification_task(
    error_id: Union[str, int],
    traceback_str: str,
    payload: MessagePayload,
    notification_service: FromDishka[NotificationService],
) -> None:
    file_data = BufferedInputFile(
        file=traceback_str.encode(),
        filename=f"error_{error_id}.txt",
    )
    payload.media = file_data
    payload.media_type = MediaType.DOCUMENT
    await notification_service.notify_super_dev(payload=payload)


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


@broker.task(retry_on_error=True)
@inject
async def send_subscription_expire_notification_task(
    remna_user: RemnaUserDto,
    ntf_type: UserNotificationType,
    i18n_kwargs: dict[str, Any],
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    telegram_id = cast(int, remna_user.telegram_id)
    i18n_kwargs_extra: dict[str, Any]

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
    elif ntf_type == UserNotificationType.EXPIRED_1_DAY_AGO:
        i18n_key = "ntf-event-user-expired-ago"
        i18n_kwargs_extra = {"value": 1}

    user = await user_service.get(telegram_id)

    if not user:
        raise ValueError(f"User '{telegram_id}' not found")

    if not user.current_subscription:
        raise ValueError(f"Current subscription for user '{telegram_id}' not found")

    i18n_kwargs_extra.update({"is_trial": user.current_subscription.is_trial})
    keyboard = get_buy_keyboard() if user.current_subscription.is_trial else get_renew_keyboard()

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key=i18n_key,
            i18n_kwargs={**i18n_kwargs, **i18n_kwargs_extra},
            reply_markup=keyboard,
            auto_delete_after=None,
            add_close_button=True,
        ),
        ntf_type=ntf_type,
    )


@broker.task(retry_on_error=True)
@inject
async def send_subscription_limited_notification_task(
    remna_user: RemnaUserDto,
    i18n_kwargs: dict[str, Any],
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    telegram_id = cast(int, remna_user.telegram_id)
    user = await user_service.get(telegram_id)

    if not user:
        raise ValueError(f"User '{telegram_id}' not found")

    if not user.current_subscription:
        raise ValueError(f"Current subscription for user '{telegram_id}' not found")

    i18n_kwargs_extra = {
        "is_trial": user.current_subscription.is_trial,
        "traffic_strategy": user.current_subscription.traffic_limit_strategy,
        "reset_time": user.current_subscription.get_expire_time,
    }

    keyboard = get_buy_keyboard() if user.current_subscription.is_trial else get_renew_keyboard()

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-event-user-limited",
            i18n_kwargs={**i18n_kwargs, **i18n_kwargs_extra},
            reply_markup=keyboard,
            auto_delete_after=None,
            add_close_button=True,
        ),
        ntf_type=UserNotificationType.LIMITED,
    )

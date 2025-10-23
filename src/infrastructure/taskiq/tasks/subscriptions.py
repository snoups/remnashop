import traceback
from typing import Optional

from aiogram.utils.formatting import Text
from dishka import FromDishka
from dishka.integrations.taskiq import inject
from loguru import logger
from remnawave.models.webhook import UserDto as RemnaUserDto

from src.core.enums import PurchaseType, SubscriptionStatus
from src.core.utils.formatters import format_bytes_to_gb, format_device_count
from src.infrastructure.database.models.dto import PlanSnapshotDto, SubscriptionDto, UserDto
from src.infrastructure.taskiq.broker import broker
from src.infrastructure.taskiq.tasks.notifications import send_error_notification_task
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.user import UserService

from .redirects import (
    redirect_to_failed_subscription_task,
    redirect_to_successed_payment_task,
    redirect_to_successed_trial_task,
)


@broker.task
@inject
async def trial_subscription_task(
    user: UserDto,
    plan: PlanSnapshotDto,
    remnawave_service: FromDishka[RemnawaveService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    logger.info(f"Task 'trial_subscription' started for user {user.telegram_id}")

    try:
        created_user = await remnawave_service.create_user(user, plan)
        trial_subscription = SubscriptionDto(
            user_remna_id=created_user.uuid,
            status=created_user.status,
            expire_at=created_user.expire_at,
            url=created_user.short_uuid,
            plan=plan,
            is_trial=True,
        )
        await subscription_service.create(user, trial_subscription)
        logger.debug(f"Created new trial subscription for user {user.telegram_id}")

        await redirect_to_successed_trial_task.kiq(user)
        logger.info(f"Trial subscription task completed successfully for user {user.telegram_id}")

    except Exception as exception:
        logger.exception(f"Failed to give trial for user {user.telegram_id}: {exception}")
        traceback_str = traceback.format_exc()
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        await send_error_notification_task.kiq(
            error_id=user.telegram_id,
            traceback_str=traceback_str,
            i18n_kwargs={
                "user": True,
                "id": str(user.telegram_id),
                "name": user.name,
                "error": f"{error_type_name}: {error_message.as_html()}",
            },
        )

        await redirect_to_failed_subscription_task.kiq(user)


@broker.task
@inject
async def purchase_subscription_task(
    user: UserDto,
    plan: PlanSnapshotDto,
    purchase_type: PurchaseType,
    subscription: Optional[SubscriptionDto],
    remnawave_service: FromDishka[RemnawaveService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    logger.info(
        f"Task 'purchase_subscription' started: {purchase_type=} for user {user.telegram_id}"
    )

    try:
        if purchase_type == PurchaseType.NEW:
            created_user = await remnawave_service.create_user(user, plan)
            new_subscription = SubscriptionDto(
                user_remna_id=created_user.uuid,
                status=created_user.status,
                expire_at=created_user.expire_at,
                url=created_user.short_uuid,
                plan=plan,
            )
            await subscription_service.create(user, new_subscription)
            logger.debug(f"Created new subscription for user {user.telegram_id}")

        elif purchase_type == PurchaseType.RENEW:
            if not subscription:
                raise Exception(f"No subscription found for renewal for user {user.telegram_id}")

            updated_user = await remnawave_service.updated_user(
                user=user,
                plan=plan,
                uuid=subscription.user_remna_id,
            )
            subscription.expire_at = updated_user.expire_at
            subscription.plan = plan
            await subscription_service.update(subscription)
            logger.debug(f"Renewed subscription for user {user.telegram_id}")

        elif purchase_type == PurchaseType.CHANGE:
            if not subscription:
                raise Exception(f"No subscription found for change for user {user.telegram_id}")

            subscription.status = SubscriptionStatus.DISABLED
            await subscription_service.update(subscription)

            updated_user = await remnawave_service.updated_user(
                user=user,
                plan=plan,
                uuid=subscription.user_remna_id,
            )
            new_subscription = SubscriptionDto(
                user_remna_id=updated_user.uuid,
                status=updated_user.status,
                expire_at=updated_user.expire_at,
                url=updated_user.short_uuid,
                plan=plan,
            )
            await subscription_service.create(user, new_subscription)
            logger.debug(f"Changed subscription for user {user.telegram_id}")

        else:
            raise Exception(f"Unknown purchase type '{purchase_type}' for user {user.telegram_id}")

        await redirect_to_successed_payment_task.kiq(user, purchase_type)
        logger.info(
            f"Purchase subscription task completed successfully for user {user.telegram_id}"
        )

    except Exception as exception:
        logger.exception(
            f"Failed to process {purchase_type=} for user {user.telegram_id}: {exception}"
        )
        traceback_str = traceback.format_exc()
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        await send_error_notification_task.kiq(
            error_id=user.telegram_id,
            traceback_str=traceback_str,
            i18n_kwargs={
                "user": True,
                "id": str(user.telegram_id),
                "name": user.name,
                "error": f"{error_type_name}: {error_message.as_html()}",
            },
        )

        await redirect_to_failed_subscription_task.kiq(user)


@broker.task
@inject
async def delete_current_subscription_task(
    user_telegram_id: int,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    logger.info(f"Task 'delete_current_subscription' started for user '{user_telegram_id}'")

    user = await user_service.get(user_telegram_id)

    if not user:
        logger.debug(f"User '{user_telegram_id}' not found, skipping deletion")
        return

    subscription = await subscription_service.get_current(user.telegram_id)

    if not subscription:
        logger.debug(f"No current subscription for user '{user.telegram_id}', skipping deletion")
        return

    subscription.status = SubscriptionStatus.DELETED
    await subscription_service.update(subscription)
    await user_service.delete_current_subscription(user.telegram_id)
    await remnawave_service.delete_user(user)


@broker.task
@inject
async def update_status_current_subscription_task(
    user_telegram_id: int,
    status: SubscriptionStatus,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    logger.info(f"Task 'update_status_current_subscription' started for user '{user_telegram_id}'")

    user = await user_service.get(user_telegram_id)

    if not user:
        logger.debug(f"User '{user_telegram_id}' not found, skipping status update")
        return

    subscription = await subscription_service.get_current(user.telegram_id)

    if not subscription:
        logger.debug(
            f"No current subscription for user '{user.telegram_id}', skipping status update"
        )
        return

    subscription.status = status
    await subscription_service.update(subscription)


@broker.task
@inject
async def sync_current_subscription_task(
    remna_user: RemnaUserDto,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    logger.info(f"Task 'sync_current_subscription' started for user '{remna_user.username}'")

    if not remna_user.telegram_id:
        logger.warning(f"Skipping sync for UUID {remna_user.uuid}: missing telegram_id")
        return

    user = await user_service.get(remna_user.telegram_id)

    if not user:
        logger.debug(f"User '{remna_user.telegram_id}' not found, skipping sync")
        return

    subscription = await subscription_service.get_current(user.telegram_id)

    if not subscription:
        logger.debug(f"No current subscription for user '{user.telegram_id}', skipping sync")
        return

    plan = subscription.plan
    device_limit = remna_user.hwid_device_limit if remna_user.hwid_device_limit else 0
    plan.traffic_limit = format_bytes_to_gb(remna_user.traffic_limit_bytes)
    plan.device_limit = format_device_count(device_limit)

    subscription.user_remna_id = remna_user.uuid
    subscription.status = SubscriptionStatus(remna_user.status)
    subscription.expire_at = remna_user.expire_at
    subscription.url = remna_user.short_uuid
    subscription.plan = plan
    await subscription_service.update(subscription)

import traceback
from datetime import timedelta
from typing import Optional, cast

from aiogram.utils.formatting import Text
from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from src.bot.keyboards import get_user_keyboard
from src.core.enums import (
    PurchaseType,
    SubscriptionStatus,
    SystemNotificationType,
    TransactionStatus,
)
from src.core.utils.formatters import (
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_traffic_limit,
)
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
    TransactionDto,
    UserDto,
)
from src.infrastructure.taskiq.broker import broker
from src.infrastructure.taskiq.tasks.notifications import (
    send_error_notification_task,
    send_system_notification_task,
)
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.transaction import TransactionService
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
    logger.info(f"Started trial for user '{user.telegram_id}'")

    try:
        created_user = await remnawave_service.create_user(user, plan)
        trial_subscription = SubscriptionDto(
            user_remna_id=created_user.uuid,
            status=created_user.status,
            is_trial=True,
            traffic_limit=plan.traffic_limit,
            device_limit=plan.device_limit,
            internal_squads=plan.internal_squads,
            expire_at=created_user.expire_at,
            url=created_user.subscription_url,
            plan=plan,
        )
        await subscription_service.create(user, trial_subscription)
        logger.debug(f"Created new trial subscription for user '{user.telegram_id}'")

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.TRIAL_GETTED,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-subscription-trial",
                i18n_kwargs={
                    "user_id": str(user.telegram_id),
                    "user_name": user.name,
                    "username": user.username or False,
                    "plan_name": plan.name,
                    "plan_type": plan.type,
                    "plan_traffic_limit": i18n_format_traffic_limit(plan.traffic_limit),
                    "plan_device_limit": i18n_format_device_limit(plan.device_limit),
                    "plan_duration": i18n_format_days(plan.duration),
                },
                reply_markup=get_user_keyboard(user.telegram_id),
            ),
        )
        await redirect_to_successed_trial_task.kiq(user)
        logger.info(f"Trial subscription task completed successfully for user '{user.telegram_id}'")

    except Exception as exception:
        logger.exception(
            f"Failed to give trial for user '{user.telegram_id}' exception: {exception}"
        )
        traceback_str = traceback.format_exc()
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        await send_error_notification_task.kiq(
            error_id=user.telegram_id,
            traceback_str=traceback_str,
            i18n_kwargs={
                "user": True,
                "user_id": str(user.telegram_id),
                "user_name": user.name,
                "username": user.username or False,
                "error": f"{error_type_name}: {error_message.as_html()}",
            },
        )

        await redirect_to_failed_subscription_task.kiq(user)


@broker.task
@inject
async def purchase_subscription_task(
    transaction: TransactionDto,
    subscription: Optional[SubscriptionDto],
    remnawave_service: FromDishka[RemnawaveService],
    subscription_service: FromDishka[SubscriptionService],
    transaction_service: FromDishka[TransactionService],
) -> None:
    purchase_type = transaction.purchase_type
    user = cast(UserDto, transaction.user)
    plan = transaction.plan

    if not user:
        logger.error(f"User not found for transaction '{transaction.id}'")
        return

    logger.info(f"Purchase subscription started: '{purchase_type}' for user '{user.telegram_id}'")
    has_trial = subscription and subscription.is_trial

    try:
        if purchase_type == PurchaseType.NEW and not has_trial:
            created_user = await remnawave_service.create_user(user, plan)
            new_subscription = SubscriptionDto(
                user_remna_id=created_user.uuid,
                status=created_user.status,
                traffic_limit=plan.traffic_limit,
                device_limit=plan.device_limit,
                internal_squads=plan.internal_squads,
                expire_at=created_user.expire_at,
                url=created_user.subscription_url,
                plan=plan,
            )
            await subscription_service.create(user, new_subscription)
            logger.debug(f"Created new subscription for user '{user.telegram_id}'")

        elif purchase_type == PurchaseType.RENEW and not has_trial:
            if not subscription:
                raise ValueError(f"No subscription found for renewal for user '{user.telegram_id}'")

            new_expire = subscription.expire_at + timedelta(days=transaction.plan.duration)
            subscription.expire_at = new_expire

            updated_user = await remnawave_service.updated_user(
                user=user,
                uuid=subscription.user_remna_id,
                subscription=subscription,
            )

            subscription.expire_at = updated_user.expire_at  # type: ignore[assignment]
            subscription.plan = plan
            await subscription_service.update(subscription)
            logger.debug(f"Renewed subscription for user '{user.telegram_id}'")

        elif purchase_type == PurchaseType.CHANGE or has_trial:
            if not subscription:
                raise ValueError(f"No subscription found for change for user '{user.telegram_id}'")

            subscription.status = SubscriptionStatus.DISABLED
            await subscription_service.update(subscription)

            updated_user = await remnawave_service.updated_user(
                user=user, uuid=subscription.user_remna_id, plan=plan, reset_traffic=True
            )
            new_subscription = SubscriptionDto(
                user_remna_id=updated_user.uuid,
                status=updated_user.status,
                traffic_limit=plan.traffic_limit,
                device_limit=plan.device_limit,
                internal_squads=plan.internal_squads,
                expire_at=updated_user.expire_at,
                url=updated_user.subscription_url,
                plan=plan,
            )
            await subscription_service.create(user, new_subscription)
            logger.debug(f"Changed subscription for user '{user.telegram_id}'")

        else:
            raise Exception(
                f"Unknown purchase type '{purchase_type}' for user '{user.telegram_id}'"
            )

        await redirect_to_successed_payment_task.kiq(user, purchase_type)
        logger.info(f"Purchase subscription task completed for user '{user.telegram_id}'")

    except Exception as exception:
        logger.exception(
            f"Failed to process purchase type '{purchase_type}' for user "
            f"'{user.telegram_id}' exception: {exception}"
        )
        traceback_str = traceback.format_exc()
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        transaction.status = TransactionStatus.FAILED
        await transaction_service.update(transaction)

        await send_error_notification_task.kiq(
            error_id=user.telegram_id,
            traceback_str=traceback_str,
            i18n_kwargs={
                "user": True,
                "user_id": str(user.telegram_id),
                "user_name": user.name,
                "username": user.username or False,
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
) -> None:
    logger.info(f"Delete current subscription started for user '{user_telegram_id}'")

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


@broker.task
@inject
async def update_status_current_subscription_task(
    user_telegram_id: int,
    status: SubscriptionStatus,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    logger.info(f"Update status current subscription started for user '{user_telegram_id}'")

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
    telegram_id: int,
    remna_subscription: RemnaSubscriptionDto,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    logger.info(f"Starting subscription sync for user '{telegram_id}'")

    user = await user_service.get(telegram_id)

    if not user:
        logger.debug(f"User '{telegram_id}' not found, skipping")
        return

    subscription = await subscription_service.get_current(user.telegram_id)

    if not subscription:
        logger.debug(f"No active subscription for user '{user.telegram_id}'")
        return

    logger.success(remna_subscription)
    subscription = subscription.apply_sync(remna_subscription)
    logger.success(subscription)
    await subscription_service.update(subscription)
    logger.info(f"Subscription for '{telegram_id}' successfully synchronized")

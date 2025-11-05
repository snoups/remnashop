import traceback
from datetime import timedelta
from typing import Optional, cast

from aiogram.utils.formatting import Text
from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from remnawave.models.webhook import UserDto as RemnaUserDto

from src.core.enums import (
    PurchaseType,
    SubscriptionStatus,
    SystemNotificationType,
    TransactionStatus,
)
from src.core.utils.formatters import (
    format_bytes_to_gb,
    format_device_count,
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_traffic_limit,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
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
    logger.info(f"[TASK] trial for user '{user.telegram_id}'")

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
        logger.debug(f"[TASK] Created new trial subscription for user '{user.telegram_id}'")

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.TRIAL_GETTED,
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
        )
        await redirect_to_successed_trial_task.kiq(user)
        logger.info(
            f"[TASK] Trial subscription task completed successfully for user '{user.telegram_id}'"
        )

    except Exception as exception:
        logger.exception(f"[TASK] Failed to give trial for user {user.telegram_id}: {exception}")
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
        logger.error(f"[TASK] User not found for transaction '{transaction.id}'")
        return

    logger.info(
        f"[TASK] 'purchase_subscription' started: {purchase_type=} for user '{user.telegram_id}'"
    )
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
            logger.debug(f"[TASK] Created new subscription for user '{user.telegram_id}'")

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
            logger.debug(f"[TASK] Renewed subscription for user '{user.telegram_id}'")

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
            logger.debug(f"[TASK] Changed subscription for user '{user.telegram_id}'")

        else:
            raise Exception(
                f"Unknown purchase type '{purchase_type}' for user '{user.telegram_id}'"
            )

        await redirect_to_successed_payment_task.kiq(user, purchase_type)
        logger.info(f"[TASK] Purchase subscription task completed for user '{user.telegram_id}'")

    except Exception as exception:
        logger.exception(
            f"[TASK] Failed to process {purchase_type=} for user {user.telegram_id}: {exception}"
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
    logger.info(f"[TASK] 'delete_current_subscription' started for user '{user_telegram_id}'")

    user = await user_service.get(user_telegram_id)

    if not user:
        logger.debug(f"[TASK] User '{user_telegram_id}' not found, skipping deletion")
        return

    subscription = await subscription_service.get_current(user.telegram_id)

    if not subscription:
        logger.debug(
            f"[TASK] No current subscription for user '{user.telegram_id}', skipping deletion"
        )
        return

    if subscription.expire_at - datetime_now() > timedelta(days=2):
        logger.debug(
            f"[TASK] Subscription for user '{user.telegram_id}' "
            f"expires in more than 2 days, skipping"
        )
        return

    subscription.status = SubscriptionStatus.DELETED
    await subscription_service.update(subscription)
    await user_service.delete_current_subscription(user.telegram_id)
    # await remnawave_service.delete_user(user)  # NOTE: Should I delete it?


@broker.task
@inject
async def update_status_current_subscription_task(
    user_telegram_id: int,
    status: SubscriptionStatus,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    logger.info(
        f"[TASK] 'update_status_current_subscription' started for user '{user_telegram_id}'"
    )

    user = await user_service.get(user_telegram_id)

    if not user:
        logger.debug(f"[TASK] User '{user_telegram_id}' not found, skipping status update")
        return

    subscription = await subscription_service.get_current(user.telegram_id)

    if not subscription:
        logger.debug(
            f"[TASK] No current subscription for user '{user.telegram_id}', skipping status update"
        )
        return

    subscription.status = status
    await subscription_service.update(subscription)


@broker.task
@inject
async def sync_current_subscription_task(  # noqa: C901
    remna_user: RemnaUserDto,
    remnawave_service: FromDishka[RemnawaveService],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    if not remna_user.telegram_id:
        logger.warning(
            f"[TASK] Skipping subscription sync for '{remna_user.uuid}': missing telegram_id"
        )
        return

    logger.info(f"[TASK] Starting subscription sync for user '{remna_user.telegram_id}'")

    user = await user_service.get(remna_user.telegram_id)

    if not user:
        logger.debug(f"[TASK] User '{remna_user.telegram_id}' not found — skipping")
        return

    subscription = await subscription_service.get_current(user.telegram_id)

    if not subscription:
        logger.debug(f"[TASK] No active subscription for user '{user.telegram_id}'")
        return

    subscription_url = await remnawave_service.get_subscription_url(user)

    if not subscription_url:
        logger.warning(f"[TASK] User '{user.telegram_id}' has not subscription_url")
        return

    device_limit = remna_user.hwid_device_limit or 0
    new_traffic_limit = format_bytes_to_gb(remna_user.traffic_limit_bytes)
    new_device_limit = format_device_count(device_limit)
    new_internal_squads = [squad.uuid for squad in remna_user.active_internal_squads]

    changes: dict[str, tuple] = {}

    if subscription.user_remna_id != remna_user.uuid:
        changes["user_remna_id"] = (subscription.user_remna_id, remna_user.uuid)
    if subscription.status != SubscriptionStatus(remna_user.status):
        changes["status"] = (subscription.status, remna_user.status)
    if subscription.expire_at != remna_user.expire_at:
        changes["expire_at"] = (subscription.expire_at, remna_user.expire_at)
    if subscription.url != subscription_url:
        changes["url"] = (subscription.url, subscription_url)
    if subscription.traffic_limit != new_traffic_limit:
        changes["traffic_limit"] = (subscription.traffic_limit, new_traffic_limit)
    if subscription.device_limit != new_device_limit:
        changes["device_limit"] = (subscription.device_limit, new_device_limit)
    if subscription.internal_squads != new_internal_squads:
        changes["internal_squads"] = (subscription.internal_squads, new_internal_squads)

    if not changes:
        logger.debug(
            f"[TASK] No differences detected for '{remna_user.telegram_id}' — skipping update"
        )
        return

    logger.info(f"[TASK] Detected {len(changes)} change(s) for '{remna_user.telegram_id}'")
    for field, (old, new) in changes.items():
        logger.debug(f"{field}: {old} → {new}")

    subscription.user_remna_id = remna_user.uuid
    subscription.status = SubscriptionStatus(remna_user.status)
    subscription.traffic_limit = new_traffic_limit
    subscription.device_limit = new_device_limit
    subscription.internal_squads = new_internal_squads
    subscription.expire_at = remna_user.expire_at
    subscription.url = subscription_url

    await subscription_service.update(subscription)
    logger.info(f"[TASK] Subscription for '{remna_user.telegram_id}' successfully synchronized")

from datetime import timedelta

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from src.core.enums import MessageEffect, ReferralRewardType, UserNotificationType
from src.core.utils.message_payload import MessagePayload
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import ReferralRewardDto
from src.infrastructure.taskiq.broker import broker
from src.services.notification import NotificationService
from src.services.referral import ReferralService
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.user import UserService


@broker.task(retry_on_error=True)
@inject
async def give_referrer_reward_task(
    user_telegram_id: int,
    reward: ReferralRewardDto,
    referred_name: str,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    notification_service: FromDishka[NotificationService],
    referral_service: FromDishka[ReferralService],
) -> None:
    logger.info(
        f"Start applying reward of '{reward.amount}' '{reward.type}' to user '{user_telegram_id}'"
    )
    user = await user_service.get(user_telegram_id)

    if not user:
        raise ValueError(
            f"User '{user_telegram_id}' not found for applying "
            f"'{reward.amount}' '{reward.type.name}' reward"
        )

    if reward.type == ReferralRewardType.POINTS:
        await user_service.add_points(user=user, points=reward.amount)
    elif reward.type == ReferralRewardType.EXTRA_DAYS:
        subscription = await subscription_service.get_current(user_telegram_id)

        if not subscription or subscription.is_trial:
            logger.warning(
                f"Current subscription not found for user '{user_telegram_id}', unable to add days"
            )
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload.not_deleted(
                    i18n_key="ntf-event-user-referral-reward-error",
                    i18n_kwargs={
                        "name": referred_name,
                        "value": reward.amount,
                    },
                ),
                ntf_type=UserNotificationType.REFERRAL_REWARD,
            )
            return

        logger.info(
            f"Current subscription found for user '{user_telegram_id}', "
            f"expire date '{subscription.expire_at}'"
        )

        base_expire_at = max(subscription.expire_at, datetime_now())
        new_expire = base_expire_at + timedelta(days=reward.amount)
        subscription.expire_at = new_expire

        await subscription_service.update(subscription)
        await remnawave_service.updated_user(
            user=user,
            uuid=subscription.user_remna_id,
            subscription=subscription,
        )
    else:
        raise ValueError(
            f"Failed to apply reward: unknown type '{reward.type}' for user '{user_telegram_id}'"
        )

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-event-user-referral-reward",
            i18n_kwargs={
                "name": referred_name,
                "value": reward.amount,
                "reward_type": reward.type,
            },
            message_effect=MessageEffect.CONFETTI,
        ),
        ntf_type=UserNotificationType.REFERRAL_REWARD,
    )
    await referral_service.mark_reward_as_issued(reward.id)  # type: ignore[arg-type]
    logger.info(f"Finished applying reward to user '{user_telegram_id}'")

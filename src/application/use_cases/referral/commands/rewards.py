from dataclasses import dataclass

from loguru import logger

from src.application.common import EventPublisher, Interactor
from src.application.common.dao import ReferralDao, SettingsDao, SubscriptionDao, UserDao
from src.application.common.uow import UnitOfWork
from src.application.dto import ReferralRewardDto, TransactionDto, UserDto
from src.application.events import ReferralRewardFailedEvent, ReferralRewardReceivedEvent
from src.application.use_cases.referral.queries.calculations import (
    CalculateReferralReward,
    CalculateReferralRewardDto,
)
from src.application.use_cases.subscription.commands.management import (
    AddSubscriptionDuration,
    AddSubscriptionDurationDto,
)
from src.application.use_cases.user.commands.profile_edit import (
    ChangeUserPoints,
    ChangeUserPointsDto,
)
from src.core.enums import PurchaseType, ReferralAccrualStrategy, ReferralLevel, ReferralRewardType


@dataclass(frozen=True)
class GiveReferrerRewardDto:
    user_telegram_id: int
    reward: ReferralRewardDto
    referred_name: str


class GiveReferrerReward(Interactor[GiveReferrerRewardDto, None]):
    required_permission = None

    def __init__(
        self,
        user_dao: UserDao,
        subscription_dao: SubscriptionDao,
        referral_dao: ReferralDao,
        event_publisher: EventPublisher,
        change_user_points: ChangeUserPoints,
        add_subscription_duration: AddSubscriptionDuration,
    ) -> None:
        self.user_dao = user_dao
        self.subscription_dao = subscription_dao
        self.referral_dao = referral_dao
        self.event_publisher = event_publisher
        self.change_user_points = change_user_points
        self.add_subscription_duration = add_subscription_duration

    async def _execute(self, actor: UserDto, data: GiveReferrerRewardDto) -> None:
        reward = data.reward

        user = await self.user_dao.get_by_telegram_id(data.user_telegram_id)
        if not user:
            logger.warning(
                f"{actor.log} User '{data.user_telegram_id}' not found, unable to apply reward"
            )
            return

        logger.info(
            f"{actor.log} Start applying reward of '{reward.amount}' "
            f"'{reward.type}' to user '{user.telegram_id}'"
        )
        if reward.type == ReferralRewardType.POINTS:
            await self.change_user_points.system(
                ChangeUserPointsDto(
                    telegram_id=user.telegram_id,
                    amount=reward.amount,
                )
            )

        elif reward.type == ReferralRewardType.EXTRA_DAYS:
            subscription = await self.subscription_dao.get_current(user.telegram_id)  # only active

            if not subscription or subscription.is_trial:
                logger.warning(
                    f"{actor.log} Current subscription not found "
                    f"for user '{user.telegram_id}', unable to add days"
                )

                event_failed = ReferralRewardFailedEvent(
                    user=user,
                    name=data.referred_name,
                    value=reward.amount,
                    reward_type=reward.type,
                )

                await self.event_publisher.publish(event_failed)
                return

            logger.info(
                f"{actor.log} Current subscription found for user '{user.telegram_id}', "
                f"expire date '{subscription.expire_at}'"
            )

            await self.add_subscription_duration.system(
                AddSubscriptionDurationDto(
                    telegram_id=user.telegram_id,
                    days=reward.amount,
                ),
            )

        else:
            raise ValueError(
                f"Failed to apply reward: unknown type '{reward.type}' "
                f"for user '{user.telegram_id}'"
            )

        event_reward = ReferralRewardReceivedEvent(
            user=user,
            name=data.referred_name,
            value=reward.amount,
            reward_type=reward.type,
        )

        await self.event_publisher.publish(event_reward)

        await self.referral_dao.mark_reward_as_issued(reward.id)  # type: ignore[arg-type]
        logger.info(f"{actor.log} Finished applying reward to user '{user.telegram_id}'")


@dataclass(frozen=True)
class AssignReferralRewardsDto:
    user: UserDto
    transaction: TransactionDto


class AssignReferralRewards(Interactor[AssignReferralRewardsDto, None]):
    required_permission = None

    def __init__(
        self,
        uow: UnitOfWork,
        settings_dao: SettingsDao,
        user_dao: UserDao,
        referral_dao: ReferralDao,
        calculate_referral_reward: CalculateReferralReward,
        give_referrer_reward: GiveReferrerReward,
    ) -> None:
        self.uow = uow
        self.settings_dao = settings_dao
        self.user_dao = user_dao
        self.referral_dao = referral_dao
        self.calculate_referral_reward = calculate_referral_reward
        self.give_referrer_reward = give_referrer_reward

    async def _execute(self, actor: UserDto, data: AssignReferralRewardsDto) -> None:
        settings = await self.settings_dao.get()

        if not settings.referral.enable:
            logger.info("Referral system is disabled; reward assignment skipped")
            return

        if (
            settings.referral.accrual_strategy == ReferralAccrualStrategy.ON_FIRST_PAYMENT
            and data.transaction.purchase_type != PurchaseType.NEW
        ):
            logger.info(
                f"Skip rewards: transaction '{data.transaction.id}' purchase type "
                f"'{data.transaction.purchase_type}' is not NEW"
            )
            return

        referral, parent = await self.referral_dao.get_referral_chain(data.user.telegram_id)

        if not referral:
            logger.info(f"User '{data.user.telegram_id}' not referred; reward assignment skipped")
            return

        reward_type = settings.referral.reward.type
        reward_chain = {ReferralLevel.FIRST: referral.referrer}

        if parent:
            reward_chain[ReferralLevel.SECOND] = parent.referrer

        for level, referrer in reward_chain.items():
            if level > settings.referral.level:
                continue

            config_value = settings.referral.reward.config.get(level)
            if config_value is None:
                logger.info(f"No reward config for level '{level.name}'")
                continue

            reward_amount = await self.calculate_referral_reward.system(
                CalculateReferralRewardDto(
                    settings=settings.referral,
                    transaction=data.transaction,
                    config_value=config_value,
                )
            )

            if not reward_amount or reward_amount <= 0:
                logger.warning(
                    f"Reward amount <= 0 for referrer '{referrer.telegram_id}', "
                    f"level '{level.name}'"
                )
                continue

            async with self.uow:
                reward = await self.referral_dao.create_reward(
                    reward=ReferralRewardDto(
                        user_telegram_id=referrer.telegram_id,
                        type=reward_type,
                        amount=reward_amount,
                        is_issued=False,
                    ),
                    referral_id=referral.id,  # type: ignore[arg-type]
                )

                await self.uow.commit()

                await self.give_referrer_reward.system(
                    GiveReferrerRewardDto(
                        user_telegram_id=referrer.telegram_id,
                        reward=reward,
                        referred_name=data.user.name,
                    )
                )

                await self.uow.commit()

            logger.info(
                f"Issued '{reward_type}' reward '{reward_amount}' for referrer "
                f"'{referrer.telegram_id}' (level '{level.name}')"
            )

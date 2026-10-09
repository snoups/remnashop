from decimal import Decimal

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import ReferralRewardType
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.referrals.dto import ReverseReferralRewardsDto
from app.modules.referrals.events import ReferralRewardReversedEvent
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserRepository


class ReverseReferralRewardsUseCase(UseCase[ReverseReferralRewardsDto, None]):
    required_permission = None

    def __init__(
        self,
        referral_repository: ReferralRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._referral_repository = referral_repository
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: ReverseReferralRewardsDto) -> None:
        rewards = await self._referral_repository.list_active_rewards_by_payment_key(
            data.payment_key
        )
        for reward in rewards:
            async with self._uow:
                if not await self._referral_repository.mark_reversed(reward.id):
                    continue
                if reward.referrer_id is None:
                    continue
                referrer = await self._user_repository.get_by_id(reward.referrer_id)
                if referrer is None:
                    continue
                taken: Decimal
                if reward.type is ReferralRewardType.EXTRA_DAYS:
                    taken = Decimal(
                        await self._user_repository.debit_bonus_days_floor(
                            reward.referrer_id, int(reward.amount)
                        )
                    )
                else:
                    taken = await self._user_repository.debit_points_floor(
                        reward.referrer_id, reward.amount
                    )
                logger.info(
                    f"Referral reward '{reward.id}' reversed: took '{taken}' of "
                    f"'{reward.amount}' from referrer '{reward.referrer_id}'"
                )
                await self._event_publisher.publish(
                    ReferralRewardReversedEvent(
                        user=referrer,
                        amount=str(taken),
                        reward_type=reward.type.value,
                        payment_key=data.payment_key,
                    )
                )

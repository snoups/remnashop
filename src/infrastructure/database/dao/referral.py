from typing import Optional, cast

from adaptix import Retort
from adaptix.conversion import ConversionRetort
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.application.common.dao import ReferralDao
from src.application.dto import ReferralDto, ReferralRewardDto
from src.core.enums import ReferralRewardType
from src.infrastructure.database.models import Referral, ReferralReward


class ReferralDaoImpl(ReferralDao):
    def __init__(
        self,
        session: AsyncSession,
        retort: Retort,
        conversion_retort: ConversionRetort,
        redis: Redis,
    ) -> None:
        self.session = session
        self.retort = retort
        self.conversion_retort = conversion_retort
        self.redis = redis

        self._convert_to_referral_dto = self.conversion_retort.get_converter(Referral, ReferralDto)
        self._convert_to_referral_list = self.conversion_retort.get_converter(
            list[Referral],
            list[ReferralDto],
        )
        self._convert_to_reward_dto = self.conversion_retort.get_converter(
            ReferralReward,
            ReferralRewardDto,
        )
        self._convert_to_reward_list = self.conversion_retort.get_converter(
            list[ReferralReward],
            list[ReferralRewardDto],
        )

    async def create_referral(self, referral: ReferralDto) -> ReferralDto:
        referral_data = self.retort.dump(referral)
        db_referral = Referral(**referral_data)

        self.session.add(db_referral)
        await self.session.flush()

        logger.debug(
            f"Created referral: referrer '{referral.referrer.telegram_id}' "
            f"invited referred '{referral.referred.telegram_id}'"
        )
        return self._convert_to_referral_dto(db_referral)

    async def get_by_referred_id(self, referred_id: int) -> Optional[ReferralDto]:
        stmt = (
            select(Referral)
            .where(Referral.referred_telegram_id == referred_id)
            .options(selectinload(Referral.referrer), selectinload(Referral.referred))
        )
        db_referral = await self.session.scalar(stmt)

        if db_referral:
            logger.debug(f"Referrer for user '{referred_id}' found")
            return self._convert_to_referral_dto(db_referral)

        logger.debug(f"Referrer for user '{referred_id}' not found")
        return None

    async def get_referrals_count(self, referrer_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Referral)
            .where(Referral.referrer_telegram_id == referrer_id)
        )
        count = await self.session.scalar(stmt) or 0

        logger.debug(f"User '{referrer_id}' has '{count}' referrals")
        return count

    async def get_referrals_list(
        self,
        referrer_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ReferralDto]:
        stmt = (
            select(Referral)
            .where(Referral.referrer_telegram_id == referrer_id)
            .options(selectinload(Referral.referred))
            .limit(limit)
            .offset(offset)
            .order_by(Referral.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        db_referrals = cast(list, result.all())

        logger.debug(
            f"Retrieved '{len(db_referrals)}' referrals for user '{referrer_id}' "
            f"with limit '{limit}' and offset '{offset}'"
        )
        return self._convert_to_referral_list(db_referrals)

    async def create_reward(
        self,
        reward: ReferralRewardDto,
        referral_id: int,
    ) -> ReferralRewardDto:
        reward_data = self.retort.dump(reward)
        db_reward = ReferralReward(**reward_data, referral_id=referral_id)

        self.session.add(db_reward)
        await self.session.flush()

        logger.debug(f"Created reward amount '{reward.amount}' for referral ID '{referral_id}'")
        return self._convert_to_reward_dto(db_reward)

    async def get_pending_rewards(self) -> list[ReferralRewardDto]:
        stmt = select(ReferralReward).where(ReferralReward.is_issued.is_(False))
        result = await self.session.scalars(stmt)
        db_rewards = cast(list, result.all())

        logger.debug(f"Retrieved '{len(db_rewards)}' pending rewards")
        return self._convert_to_reward_list(db_rewards)

    async def mark_reward_as_issued(self, reward_id: int) -> None:
        stmt = update(ReferralReward).where(ReferralReward.id == reward_id).values(is_issued=True)
        await self.session.execute(stmt)
        logger.debug(f"Reward '{reward_id}' marked as issued")

    async def get_total_rewards_amount(
        self,
        telegram_id: int,
        reward_type: ReferralRewardType,
    ) -> int:
        stmt = select(func.sum(ReferralReward.amount)).where(
            ReferralReward.user_telegram_id == telegram_id,
            ReferralReward.type == reward_type,
            ReferralReward.is_issued.is_(True),
        )
        total = await self.session.scalar(stmt) or 0

        logger.debug(
            f"Total rewards amount for user '{telegram_id}' with type '{reward_type}' is '{total}'"
        )
        return int(total)

    async def get_referral_chain(
        self,
        referred_id: int,
    ) -> tuple[Optional[ReferralDto], Optional[ReferralDto]]:
        first_level = await self.get_by_referred_id(referred_id)
        if not first_level:
            return None, None

        second_level = await self.get_by_referred_id(first_level.referrer.telegram_id)

        logger.debug(
            f"Referral chain for user '{referred_id}': "
            f"level 1 '{first_level.referrer.telegram_id}', "
            f"level 2 '{second_level.referrer.telegram_id if second_level else 'none'}'"
        )

        return first_level, second_level

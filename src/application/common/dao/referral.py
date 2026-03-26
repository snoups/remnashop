from typing import Optional, Protocol, runtime_checkable

from src.application.dto import ReferralDto, ReferralRewardDto, ReferralStatisticsDto
from src.core.enums import ReferralRewardType


@runtime_checkable
class ReferralDao(Protocol):
    async def create_referral(self, referral: ReferralDto) -> ReferralDto: ...

    async def get_by_referred_id(self, referred_id: int) -> Optional[ReferralDto]: ...

    async def get_referrals_count(self, referrer_id: int) -> int: ...

    async def get_referrals_list(
        self,
        referrer_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ReferralDto]: ...

    async def create_reward(
        self,
        reward: ReferralRewardDto,
        referral_id: int,
    ) -> ReferralRewardDto: ...

    async def get_pending_rewards(self) -> list[ReferralRewardDto]: ...

    async def mark_reward_as_issued(self, reward_id: int) -> None: ...

    async def get_total_rewards_amount(
        self,
        telegram_id: int,
        reward_type: ReferralRewardType,
    ) -> int: ...

    async def get_referral_chain(
        self,
        referred_id: int,
    ) -> tuple[Optional[ReferralDto], Optional[ReferralDto]]: ...

    async def get_stats(self) -> ReferralStatisticsDto: ...

    async def get_user_referral_stats(self, telegram_id: int) -> dict: ...

    async def get_referrals_with_payment_count(self, referrer_id: int) -> int: ...

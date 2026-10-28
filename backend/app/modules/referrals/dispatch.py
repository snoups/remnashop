from typing import Protocol


class BonusRenewalDispatch(Protocol):
    async def kiq(
        self, *, user_id: int, subscription_id: int, days: int, idempotency_key: str
    ) -> object: ...


class AssignReferralRewardsDispatch(Protocol):
    async def kiq(
        self, *, user_id: int, subscription_id: int, is_new_purchase: bool, payment_key: str
    ) -> object: ...


class AttachReferralDispatch(Protocol):
    async def kiq(self, *, user_id: int, referral_code: str) -> object: ...


class ReverseReferralRewardsDispatch(Protocol):
    async def kiq(self, *, payment_key: str) -> object: ...

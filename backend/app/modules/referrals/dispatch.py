from typing import Protocol


class BonusRenewalDispatch(Protocol):
    async def kiq(
        self, *, user_id: int, subscription_id: int, days: int, idempotency_key: str
    ) -> object: ...

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol


class ReferrerLookup(Protocol):
    async def has_referrer(self, user_id: int) -> bool: ...


@dataclass(frozen=True, kw_only=True)
class SpentPurchaseDiscount:
    user_id: int
    percent: int
    promocode_id: Optional[int]
    from_promocode: bool


class OrderFailer(Protocol):
    async def fail_unpaid_free_order(self, idempotency_key: str) -> Optional[SpentPurchaseDiscount]:
        """The one-shot discount to hand back when this call failed the order."""
        ...


class OpenOrderCounter(Protocol):
    # NEW orders that can still become a subscription: unexpired PENDING or PAID-unlinked
    async def count_open_new_orders(
        self, user_id: int, now: datetime, *, exclude_key: Optional[str] = None
    ) -> int: ...


class RecurringPaymentCloser(Protocol):
    async def close_for_plan_change(self, subscription_id: int) -> None: ...

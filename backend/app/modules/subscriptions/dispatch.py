from typing import Any, Optional, Protocol


class PurchaseSubscriptionDispatch(Protocol):
    async def kiq(
        self,
        *,
        user_id: int,
        plan_snapshot: dict[str, Any],
        duration_days: int,
        price_paid: str,
        currency: str,
        purchase_type: str,
        target_subscription_id: Optional[int] = None,
        base_price: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> object: ...


class GrantAddOnDispatch(Protocol):
    async def kiq(
        self, *, subscription_id: int, addon_id: int, idempotency_key: Optional[str] = None
    ) -> object: ...

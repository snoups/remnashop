from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from app.core.enums import Currency, PurchaseType
from app.modules.transactions.fulfillment import dispatch_fulfillment


class _Dispatch:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def kiq(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


async def test_fulfilment_carries_the_credit_fixed_at_checkout() -> None:
    dispatch = _Dispatch()
    order = SimpleNamespace(
        user_id=1,
        plan_snapshot=SimpleNamespace(to_json=lambda: {}),
        duration_days=0,
        final_price=Decimal("500.00"),
        base_price=Decimal("3000.00"),
        change_credit=Decimal("2500.00"),
        currency=Currency.RUB,
        purchase_type=PurchaseType.CHANGE,
        target_subscription_id=7,
        idempotency_key="order-key",
    )

    await dispatch_fulfillment(dispatch, order)  # type: ignore[arg-type]

    assert dispatch.calls[0]["change_credit"] == "2500.00"

from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.account_merge import AccountsMergedEvent
from app.modules.loyalty.tasks import recalculate_loyalty_discounts_task
from app.modules.subscriptions import (
    SubscriptionChangedEvent,
    SubscriptionPurchasedEvent,
    SubscriptionRenewedEvent,
)
from app.modules.transactions import TransactionRefundedEvent


async def _recalculate_buyer(entry: StoredEvent) -> None:
    await recalculate_loyalty_discounts_task.kiq(  # type: ignore[call-overload]
        user_ids=[entry.payload["user"]["id"]]
    )


async def _recalculate_refunded(entry: StoredEvent) -> None:
    await recalculate_loyalty_discounts_task.kiq(  # type: ignore[call-overload]
        user_ids=[entry.payload["user_id"]]
    )


async def _recalculate_merged(entry: StoredEvent) -> None:
    await recalculate_loyalty_discounts_task.kiq(  # type: ignore[call-overload]
        user_ids=[entry.payload["target"]["id"]]
    )


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(SubscriptionPurchasedEvent, _recalculate_buyer)
    bus.subscribe(SubscriptionRenewedEvent, _recalculate_buyer)
    bus.subscribe(SubscriptionChangedEvent, _recalculate_buyer)
    bus.subscribe(TransactionRefundedEvent, _recalculate_refunded)
    bus.subscribe(AccountsMergedEvent, _recalculate_merged)

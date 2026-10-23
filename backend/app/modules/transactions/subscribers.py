from typing import Union

from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.settings import AccessSettingsChangedEvent
from app.modules.subscriptions import (
    SubscriptionChangedEvent,
    SubscriptionPurchasedEvent,
    SubscriptionRenewedEvent,
)
from app.modules.transactions.tasks import mark_order_fulfilled_task, notify_payment_waitlist_task


async def _notify_waitlist(event: AccessSettingsChangedEvent, entry: StoredEvent) -> None:
    if event.payments_reenabled:
        await notify_payment_waitlist_task.kiq()  # type: ignore[call-overload]


async def _mark_fulfilled(
    event: Union[SubscriptionPurchasedEvent, SubscriptionRenewedEvent, SubscriptionChangedEvent],
    entry: StoredEvent,
) -> None:
    if event.payment_key is not None:
        await mark_order_fulfilled_task.kiq(  # type: ignore[call-overload]
            payment_key=event.payment_key, subscription_id=event.subscription_id
        )


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(AccessSettingsChangedEvent, _notify_waitlist)
    bus.subscribe(SubscriptionPurchasedEvent, _mark_fulfilled)
    bus.subscribe(SubscriptionRenewedEvent, _mark_fulfilled)
    bus.subscribe(SubscriptionChangedEvent, _mark_fulfilled)

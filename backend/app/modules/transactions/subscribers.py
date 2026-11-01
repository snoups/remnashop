from typing import Final, Union, cast

from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.settings import AccessSettingsChangedEvent
from app.modules.subscriptions import (
    SubscriptionChangedEvent,
    SubscriptionPurchasedEvent,
    SubscriptionRenewedEvent,
)
from app.modules.transactions.dispatch import (
    MarkOrderFulfilledDispatch,
    NotifyPaymentWaitlistDispatch,
)
from app.modules.transactions.tasks import mark_order_fulfilled_task, notify_payment_waitlist_task

_notify_payment_waitlist: Final[NotifyPaymentWaitlistDispatch] = cast(
    NotifyPaymentWaitlistDispatch, notify_payment_waitlist_task
)
_mark_order_fulfilled: Final[MarkOrderFulfilledDispatch] = cast(
    MarkOrderFulfilledDispatch, mark_order_fulfilled_task
)


async def _notify_waitlist(event: AccessSettingsChangedEvent, entry: StoredEvent) -> None:
    if event.payments_reenabled:
        await _notify_payment_waitlist.kiq(outbox_id=entry.outbox_id)


async def _mark_fulfilled(
    event: Union[SubscriptionPurchasedEvent, SubscriptionRenewedEvent, SubscriptionChangedEvent],
    entry: StoredEvent,
) -> None:
    if event.payment_key is not None:
        await _mark_order_fulfilled.kiq(
            payment_key=event.payment_key, subscription_id=event.subscription_id
        )


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(AccessSettingsChangedEvent, _notify_waitlist)
    bus.subscribe(SubscriptionPurchasedEvent, _mark_fulfilled)
    bus.subscribe(SubscriptionRenewedEvent, _mark_fulfilled)
    bus.subscribe(SubscriptionChangedEvent, _mark_fulfilled)

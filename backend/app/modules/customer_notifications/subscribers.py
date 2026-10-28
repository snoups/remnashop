from typing import Any, Final, Optional, Union, cast

from app.core.event_bus import EventBus
from app.core.events import StoredEvent, UserEvent
from app.modules.account_merge import AccountsMergedEvent
from app.modules.cabinet_auth import CabinetNewDeviceSignInEvent
from app.modules.customer_notifications.dispatch import (
    NotifyCustomerDispatch,
    ShowPaymentCanceledDispatch,
)
from app.modules.customer_notifications.tasks import (
    notify_customer_task,
    show_payment_canceled_task,
)
from app.modules.promocodes import PromocodeDiscountExpiringEvent
from app.modules.referrals import InviteeRewardIssuedEvent, ReferralRewardIssuedEvent
from app.modules.subscriptions import (
    SubscriptionAddOnGrantedEvent,
    SubscriptionChangedEvent,
    SubscriptionExpiredAgoEvent,
    SubscriptionExpiredEvent,
    SubscriptionExpiringEvent,
    SubscriptionGrantedEvent,
    SubscriptionNotConnectedEvent,
    SubscriptionPurchasedEvent,
    SubscriptionRenewedEvent,
    SubscriptionTrafficLimitedEvent,
    SubscriptionTrafficThresholdEvent,
    TorrentBlockerReportEvent,
)
from app.modules.transactions import (
    PaidOrderNotFulfilledEvent,
    TransactionCanceledEvent,
    TransactionExpiredEvent,
    TransactionPartiallyRefundedEvent,
    TransactionRefundedEvent,
)

_notify_customer: Final[NotifyCustomerDispatch] = cast(NotifyCustomerDispatch, notify_customer_task)
_show_payment_canceled: Final[ShowPaymentCanceledDispatch] = cast(
    ShowPaymentCanceledDispatch, show_payment_canceled_task
)


async def _notify(
    entry: StoredEvent,
    user_id: int,
    args: dict[str, Any],
    payment_key: Optional[str] = None,
    subscription_id: Optional[int] = None,
) -> None:
    # the system actor owns nothing
    if user_id <= 0:
        return
    await _notify_customer.kiq(
        user_id=user_id,
        event_type=entry.event_type,
        outbox_id=entry.outbox_id,
        args=args,
        payment_key=payment_key,
        subscription_id=subscription_id,
    )


async def _on_purchase(event: UserEvent, entry: StoredEvent) -> None:
    await _notify(entry, event.user.id, {})


async def _on_paid(
    event: Union[SubscriptionPurchasedEvent, SubscriptionChangedEvent], entry: StoredEvent
) -> None:
    await _notify(entry, event.user.id, {}, event.payment_key)


async def _on_renewed(event: SubscriptionRenewedEvent, entry: StoredEvent) -> None:
    await _notify(entry, event.user.id, {"duration_days": event.duration_days}, event.payment_key)


async def _on_addon(event: SubscriptionAddOnGrantedEvent, entry: StoredEvent) -> None:
    # the owner is `target`; `user` is the system actor on the promocode path
    await _notify(entry, (event.target or event.user).id, {})


async def _on_granted(event: SubscriptionGrantedEvent, entry: StoredEvent) -> None:
    await _notify(entry, event.target.id, {"duration_days": event.duration_days})


async def _on_refund(
    event: Union[TransactionRefundedEvent, TransactionPartiallyRefundedEvent],
    entry: StoredEvent,
) -> None:
    await _notify(entry, event.user_id, {"amount": event.amount, "currency": event.currency})


async def _on_not_fulfilled(event: PaidOrderNotFulfilledEvent, entry: StoredEvent) -> None:
    await _notify(
        entry,
        event.user_id,
        {"amount": event.amount, "currency": event.currency},
        event.payment_key,
    )


async def _on_abandoned(
    event: Union[TransactionCanceledEvent, TransactionExpiredEvent], entry: StoredEvent
) -> None:
    await _show_payment_canceled.kiq(order_id=event.order_id)


async def _on_hours(
    event: Union[
        SubscriptionExpiringEvent, SubscriptionNotConnectedEvent, SubscriptionExpiredAgoEvent
    ],
    entry: StoredEvent,
) -> None:
    await _notify(
        entry, event.user.id, {"hours": event.hours}, subscription_id=event.subscription_id
    )


async def _on_lapsed(
    event: Union[SubscriptionExpiredEvent, SubscriptionTrafficLimitedEvent], entry: StoredEvent
) -> None:
    await _notify(entry, event.user.id, {}, subscription_id=event.subscription_id)


def _amount(value: Union[str, int]) -> Union[str, int]:
    # ftl plural selectors only match numbers, a numeric string would fall to [other]
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value


async def _on_discount_expiring(event: PromocodeDiscountExpiringEvent, entry: StoredEvent) -> None:
    await _notify(
        entry,
        event.user.id,
        {"code": event.code, "percent": event.percent, "hours": event.hours},
    )


async def _on_reward(
    event: Union[ReferralRewardIssuedEvent, InviteeRewardIssuedEvent], entry: StoredEvent
) -> None:
    await _notify(
        entry, event.user.id, {"reward_type": event.reward_type, "amount": _amount(event.amount)}
    )


async def _on_new_device(event: CabinetNewDeviceSignInEvent, entry: StoredEvent) -> None:
    await _notify(entry, event.user.id, {"browser": event.browser, "ip": event.ip_address or "—"})


async def _on_accounts_merged(event: AccountsMergedEvent, entry: StoredEvent) -> None:
    # an admin merge is not the customer's own doing, no notice
    if event.actor.id == event.target.id:
        await _notify(entry, event.target.id, {})


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(SubscriptionPurchasedEvent, _on_paid)
    bus.subscribe(SubscriptionChangedEvent, _on_paid)
    bus.subscribe(SubscriptionRenewedEvent, _on_renewed)
    bus.subscribe(SubscriptionAddOnGrantedEvent, _on_addon)
    bus.subscribe(SubscriptionGrantedEvent, _on_granted)
    bus.subscribe(TransactionRefundedEvent, _on_refund)
    bus.subscribe(TransactionPartiallyRefundedEvent, _on_refund)
    bus.subscribe(PaidOrderNotFulfilledEvent, _on_not_fulfilled)
    bus.subscribe(TransactionCanceledEvent, _on_abandoned)
    bus.subscribe(TransactionExpiredEvent, _on_abandoned)
    bus.subscribe(SubscriptionExpiringEvent, _on_hours)
    bus.subscribe(SubscriptionExpiredEvent, _on_lapsed)
    bus.subscribe(SubscriptionTrafficLimitedEvent, _on_lapsed)
    bus.subscribe(SubscriptionTrafficThresholdEvent, _on_purchase)
    bus.subscribe(SubscriptionNotConnectedEvent, _on_hours)
    bus.subscribe(SubscriptionExpiredAgoEvent, _on_hours)
    bus.subscribe(TorrentBlockerReportEvent, _on_purchase)
    bus.subscribe(CabinetNewDeviceSignInEvent, _on_new_device)
    bus.subscribe(AccountsMergedEvent, _on_accounts_merged)
    bus.subscribe(ReferralRewardIssuedEvent, _on_reward)
    bus.subscribe(InviteeRewardIssuedEvent, _on_reward)
    bus.subscribe(PromocodeDiscountExpiringEvent, _on_discount_expiring)

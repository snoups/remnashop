from typing import Any

from app.core.event_bus import EventBus
from app.core.events import StoredEvent
from app.modules.cabinet_auth import CabinetNewDeviceSignInEvent
from app.modules.customer_notifications.tasks import notify_customer_task
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
from app.modules.transactions import TransactionPartiallyRefundedEvent, TransactionRefundedEvent


async def _notify(entry: StoredEvent, user_id: int, args: dict[str, Any]) -> None:
    # the system actor owns nothing
    if user_id <= 0:
        return
    await notify_customer_task.kiq(  # type: ignore[call-overload]
        user_id=user_id, event_type=entry.event_type, outbox_id=entry.outbox_id, args=args
    )


async def _on_purchase(entry: StoredEvent) -> None:
    await _notify(entry, entry.payload["user"]["id"], {})


async def _on_renewed(entry: StoredEvent) -> None:
    await _notify(
        entry, entry.payload["user"]["id"], {"duration_days": entry.payload["duration_days"]}
    )


async def _on_addon(entry: StoredEvent) -> None:
    # the owner is `target`; `user` is the system actor on the promocode path
    owner = entry.payload.get("target") or entry.payload["user"]
    await _notify(entry, owner["id"], {})


async def _on_granted(entry: StoredEvent) -> None:
    await _notify(
        entry, entry.payload["target"]["id"], {"duration_days": entry.payload["duration_days"]}
    )


async def _on_refund(entry: StoredEvent) -> None:
    await _notify(
        entry,
        entry.payload["user_id"],
        {"amount": entry.payload["amount"], "currency": entry.payload["currency"]},
    )


async def _on_expiring(entry: StoredEvent) -> None:
    await _notify(entry, entry.payload["user"]["id"], {"hours": entry.payload["hours"]})


async def _on_hours(entry: StoredEvent) -> None:
    await _notify(entry, entry.payload["user"]["id"], {"hours": entry.payload["hours"]})


def _amount(value: str | int) -> str | int:
    # ftl plural selectors only match numbers, a numeric string would fall to [other]
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value


async def _on_reward(entry: StoredEvent) -> None:
    await _notify(
        entry,
        entry.payload["user"]["id"],
        {"reward_type": entry.payload["reward_type"], "amount": _amount(entry.payload["amount"])},
    )


async def _on_new_device(entry: StoredEvent) -> None:
    await _notify(
        entry,
        entry.payload["user"]["id"],
        {"browser": entry.payload["browser"], "ip": entry.ip_address or "—"},
    )


def register_subscribers(bus: EventBus) -> None:
    bus.subscribe(SubscriptionPurchasedEvent, _on_purchase)
    bus.subscribe(SubscriptionChangedEvent, _on_purchase)
    bus.subscribe(SubscriptionRenewedEvent, _on_renewed)
    bus.subscribe(SubscriptionAddOnGrantedEvent, _on_addon)
    bus.subscribe(SubscriptionGrantedEvent, _on_granted)
    bus.subscribe(TransactionRefundedEvent, _on_refund)
    bus.subscribe(TransactionPartiallyRefundedEvent, _on_refund)
    bus.subscribe(SubscriptionExpiringEvent, _on_expiring)
    bus.subscribe(SubscriptionExpiredEvent, _on_purchase)
    bus.subscribe(SubscriptionTrafficLimitedEvent, _on_purchase)
    bus.subscribe(SubscriptionTrafficThresholdEvent, _on_purchase)
    bus.subscribe(SubscriptionNotConnectedEvent, _on_hours)
    bus.subscribe(SubscriptionExpiredAgoEvent, _on_hours)
    bus.subscribe(TorrentBlockerReportEvent, _on_purchase)
    bus.subscribe(CabinetNewDeviceSignInEvent, _on_new_device)
    bus.subscribe(ReferralRewardIssuedEvent, _on_reward)
    bus.subscribe(InviteeRewardIssuedEvent, _on_reward)

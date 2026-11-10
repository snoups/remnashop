from dataclasses import replace
from datetime import timedelta
from typing import Any
from unittest.mock import ANY, AsyncMock, patch

import pytest

from app.core.actor import SyntheticActor
from app.core.enums import (
    AddOnType,
    Currency,
    Locale,
    PaymentGatewayType,
    PurchaseType,
    ReferralRewardType,
    Role,
)
from app.core.event_bus import EventBus
from app.core.events import BaseEvent
from app.modules.account_merge import AccountsMergedEvent
from app.modules.customer_notifications.subscribers import register_subscribers
from app.modules.referrals import (
    InviteeRewardIssuedEvent,
    ReferralAttachedEvent,
    ReferralRewardIssuedEvent,
)
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
from app.modules.users import UserDto
from tests.fakes.events import stored_event

_KIQ = "app.modules.customer_notifications.tasks.notify_customer_task.kiq"
_CANCEL_KIQ = "app.modules.customer_notifications.tasks.show_payment_canceled_task.kiq"


def _user(user_id: int) -> UserDto:
    return UserDto(
        id=user_id, login=f"u{user_id}", name=f"u{user_id}", role=Role.USER, language=Locale.EN
    )


_SYSTEM = SyntheticActor(id=0, role=Role.SYSTEM, name="SYSTEM", is_privileged=True, log="[SYSTEM]")
_SUB: dict[str, Any] = {"subscription_id": 1}


async def _dispatch(event: BaseEvent) -> AsyncMock:
    bus = EventBus()
    register_subscribers(bus)
    with patch(_KIQ, new_callable=AsyncMock) as kiq:
        assert await bus.dispatch_stored(stored_event(event)) is None
    return kiq


@pytest.mark.parametrize(
    ("event", "user_id", "args"),
    [
        (
            SubscriptionPurchasedEvent(
                user=_user(7), plan_id=1, purchase_type=PurchaseType.NEW, **_SUB
            ),
            7,
            {"paid": "no", "is_trial": "no"},
        ),
        (
            SubscriptionChangedEvent(
                user=_user(7), previous_subscription_id=2, previous_plan_snapshot={}, **_SUB
            ),
            7,
            {"paid": "no"},
        ),
        (
            SubscriptionRenewedEvent(user=_user(7), duration_days=30, **_SUB),
            7,
            {"duration_days": 30, "paid": "no"},
        ),
        (
            SubscriptionAddOnGrantedEvent(
                user=_SYSTEM,
                target=_user(9),
                addon_id=1,
                addon_type=AddOnType.TRAFFIC,
                amount=10,
                **_SUB,
            ),
            9,
            {"addon_type": AddOnType.TRAFFIC, "amount": 10},
        ),
        (
            SubscriptionAddOnGrantedEvent(
                user=_user(7),
                target=None,
                addon_id=1,
                addon_type=AddOnType.DEVICES,
                amount=2,
                **_SUB,
            ),
            7,
            {"addon_type": AddOnType.DEVICES, "amount": 2},
        ),
        (
            SubscriptionGrantedEvent(
                actor=_user(1), target=_user(9), plan_id=1, duration_days=5, **_SUB
            ),
            9,
            {"duration_days": 5},
        ),
        (
            TransactionRefundedEvent(
                order_id=1,
                user_id=3,
                payment_key="k",
                gateway_type=PaymentGatewayType.YOOKASSA,
                amount="10.00",
                currency=Currency.USD,
            ),
            3,
            {"order_id": 1, "amount": "10.00", "currency": Currency.USD},
        ),
        (
            TransactionPartiallyRefundedEvent(
                order_id=1,
                user_id=3,
                gateway_type=PaymentGatewayType.YOOKASSA,
                amount="1.00",
                currency=Currency.USD,
            ),
            3,
            {"order_id": 1, "amount": "1.00", "currency": Currency.USD},
        ),
        (
            ReferralRewardIssuedEvent(
                user=_user(7), level=1, reward_type=ReferralRewardType.EXTRA_DAYS, amount="5"
            ),
            7,
            {
                "reward_type": ReferralRewardType.EXTRA_DAYS,
                "amount": 5,
                "name": "",
                "has_name": "no",
            },
        ),
        (
            ReferralRewardIssuedEvent(
                user=_user(7), level=2, reward_type=ReferralRewardType.POINTS, amount="12.50"
            ),
            7,
            {
                "reward_type": ReferralRewardType.POINTS,
                "amount": "12.50",
                "name": "",
                "has_name": "no",
            },
        ),
        (SubscriptionNotConnectedEvent(user=_user(7), hours=24, **_SUB), 7, {"hours": 24}),
        (SubscriptionExpiredAgoEvent(user=_user(7), hours=24, **_SUB), 7, {"hours": 24}),
        (
            TorrentBlockerReportEvent(
                user=_user(7), node_name="n", destination="d", blocked_until="t", **_SUB
            ),
            7,
            {},
        ),
        (
            InviteeRewardIssuedEvent(
                user=_user(7), reward_type=ReferralRewardType.EXTRA_DAYS, amount=3
            ),
            7,
            {"reward_type": ReferralRewardType.EXTRA_DAYS, "amount": 3},
        ),
        (
            PaidOrderNotFulfilledEvent(
                order_id=4,
                user_id=3,
                payment_key="k",
                gateway_type=PaymentGatewayType.YOOKASSA,
                amount="10.00",
                currency=Currency.USD,
            ),
            3,
            {"order_id": 4, "amount": "10.00", "currency": Currency.USD},
        ),
    ],
    ids=lambda value: type(value).__name__ if isinstance(value, BaseEvent) else "",
)
async def test_event_enqueues_notification(
    event: BaseEvent, user_id: int, args: dict[str, Any]
) -> None:
    kiq = await _dispatch(event)

    kiq.assert_awaited_once_with(
        user_id=user_id,
        event_type=event.event_type,
        outbox_id=5,
        args=args,
        payment_key=ANY,
        subscription_id=ANY,
    )


async def test_system_actor_owner_is_skipped() -> None:
    event = SubscriptionPurchasedEvent(
        user=_SYSTEM, plan_id=1, purchase_type=PurchaseType.NEW, **_SUB
    )

    kiq = await _dispatch(event)

    kiq.assert_not_awaited()


@pytest.mark.parametrize(("actor_id", "notified"), [(7, True), (1, False)])
async def test_merge_notifies_only_on_self_merge(actor_id: int, notified: bool) -> None:
    event = AccountsMergedEvent(actor=_user(actor_id), target=_user(7), source=_user(8))

    kiq = await _dispatch(event)

    if notified:
        kiq.assert_awaited_once_with(
            user_id=7,
            event_type="AccountsMergedEvent",
            outbox_id=5,
            args={},
            payment_key=None,
            subscription_id=None,
        )
    else:
        kiq.assert_not_awaited()


@pytest.mark.parametrize(
    "event",
    [
        SubscriptionPurchasedEvent(
            user=_user(7), plan_id=1, purchase_type=PurchaseType.NEW, payment_key="k", **_SUB
        ),
        SubscriptionChangedEvent(
            user=_user(7),
            previous_subscription_id=2,
            previous_plan_snapshot={},
            payment_key="k",
            **_SUB,
        ),
        SubscriptionRenewedEvent(user=_user(7), duration_days=30, payment_key="k", **_SUB),
        PaidOrderNotFulfilledEvent(
            order_id=1,
            user_id=7,
            payment_key="k",
            gateway_type=PaymentGatewayType.YOOKASSA,
            amount="10.00",
            currency=Currency.USD,
        ),
    ],
    ids=lambda event: type(event).__name__,
)
async def test_paid_event_passes_payment_key(event: BaseEvent) -> None:
    kiq = await _dispatch(event)

    assert kiq.await_args.kwargs["payment_key"] == "k"


@pytest.mark.parametrize("event_class", [TransactionCanceledEvent, TransactionExpiredEvent])
async def test_abandoned_order_shows_cancel_window(event_class: type[BaseEvent]) -> None:
    bus = EventBus()
    register_subscribers(bus)
    with patch(_CANCEL_KIQ, new_callable=AsyncMock) as kiq:
        await bus.dispatch_stored(stored_event(event_class(order_id=4, user_id=7)))  # type: ignore[call-arg]

    kiq.assert_awaited_once_with(order_id=4)


@pytest.mark.parametrize(
    "event",
    [
        SubscriptionExpiringEvent(user=_user(7), hours=24, **_SUB),
        SubscriptionExpiredEvent(user=_user(7), **_SUB),
        SubscriptionTrafficLimitedEvent(user=_user(7), **_SUB),
    ],
    ids=lambda event: type(event).__name__,
)
async def test_lapsing_subscription_is_named_for_its_renew_button(event: BaseEvent) -> None:
    kiq = await _dispatch(event)

    assert kiq.await_args.kwargs["subscription_id"] == 1


@pytest.mark.parametrize(
    "event",
    [
        SubscriptionPurchasedEvent(
            user=_user(7), plan_id=1, purchase_type=PurchaseType.NEW, **_SUB
        ),
        SubscriptionChangedEvent(
            user=_user(7), previous_subscription_id=2, previous_plan_snapshot={}, **_SUB
        ),
        SubscriptionRenewedEvent(user=_user(7), duration_days=30, **_SUB),
        SubscriptionAddOnGrantedEvent(
            user=_SYSTEM,
            target=_user(9),
            addon_id=1,
            addon_type=AddOnType.TRAFFIC,
            amount=10,
            **_SUB,
        ),
        SubscriptionGrantedEvent(
            actor=_user(1), target=_user(9), plan_id=1, duration_days=5, **_SUB
        ),
        SubscriptionTrafficThresholdEvent(user=_user(7), **_SUB),
        TorrentBlockerReportEvent(
            user=_user(7), node_name="n", destination="d", blocked_until="t", **_SUB
        ),
    ],
    ids=lambda event: type(event).__name__,
)
async def test_subscription_event_names_its_subscription(event: BaseEvent) -> None:
    kiq = await _dispatch(event)

    # a plan change names the new subscription, not the replaced one
    assert kiq.await_args.kwargs["subscription_id"] == 1


@pytest.mark.parametrize(
    ("minutes", "args"),
    [
        (30, {"block_unit": "minute", "block_span": 30}),
        (90, {"block_unit": "hour", "block_span": 2}),
        (-5, {}),
    ],
)
async def test_torrent_block_says_how_long_it_lasts(minutes: int, args: dict[str, Any]) -> None:
    event = TorrentBlockerReportEvent(
        user=_user(7), node_name="n", destination="d", blocked_until="t", **_SUB
    )
    until = event.occurred_at + timedelta(minutes=minutes)
    event = replace(event, blocked_until=until.isoformat())

    kiq = await _dispatch(event)

    assert kiq.await_args.kwargs["args"] == args


@pytest.mark.parametrize("rewarded", [True, False])
async def test_the_referrer_hears_about_the_friend_who_joined(rewarded: bool) -> None:
    friend = _user(9)
    event = ReferralAttachedEvent(user=friend, referrer_id=7, rewarded=rewarded)

    kiq = await _dispatch(event)

    kiq.assert_awaited_once_with(
        user_id=7,
        event_type="ReferralAttachedEvent",
        outbox_id=5,
        args={"name": friend.name, "rewarded": "yes" if rewarded else "no"},
        payment_key=None,
        subscription_id=None,
    )


async def test_a_reward_names_the_invitee_who_paid() -> None:
    event = ReferralRewardIssuedEvent(
        user=_user(7),
        level=1,
        reward_type=ReferralRewardType.EXTRA_DAYS,
        amount="5",
        invitee_name="Ivan",
    )

    kiq = await _dispatch(event)

    assert kiq.await_args.kwargs["args"]["name"] == "Ivan"
    assert kiq.await_args.kwargs["args"]["has_name"] == "yes"

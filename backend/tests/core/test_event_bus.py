from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar

import pytest

from app.core.enums import CabinetSignInMethod, Locale, OAuthProvider, ReferralRewardType, Role
from app.core.event_bus import EventBus
from app.core.events import BaseEvent, EventCategory, StoredEvent
from app.core.outbox_event_publisher import _build_payload
from app.modules.account_merge.events import AccountsMergedEvent
from app.modules.advertising.tasks import record_ad_link_attribution_task
from app.modules.auth.events import (
    BootstrapConflictEvent,
    LoginFailedEvent,
    LoginSucceededEvent,
    OwnerBootstrappedEvent,
    SessionRevokedEvent,
    SessionTheftDetectedEvent,
    UserSessionRevokedByAdminEvent,
)
from app.modules.cabinet_auth.events import CabinetNewDeviceSignInEvent
from app.modules.customer_notifications.tasks import (
    notify_customer_task,
    show_payment_canceled_task,
)
from app.modules.loyalty.tasks import recalculate_loyalty_discounts_task
from app.modules.notifications.tasks import deliver_notification_task
from app.modules.oauth.events import (
    OAuthIdentityConnectedEvent,
    OAuthIdentityDisconnectedEvent,
    OAuthLoginFailedEvent,
    OAuthLoginSucceededEvent,
)
from app.modules.promocodes.events import PromocodeDiscountExpiringEvent
from app.modules.referrals.events import InviteeRewardIssuedEvent, ReferralRewardIssuedEvent
from app.modules.referrals.tasks import (
    assign_referral_rewards_task,
    attach_referral_on_registration_task,
    reverse_referral_rewards_task,
)
from app.modules.settings.events import AccessSettingsChangedEvent
from app.modules.subscriptions.events import (
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
from app.modules.transactions.events import (
    PaidOrderNotFulfilledEvent,
    TransactionCanceledEvent,
    TransactionExpiredEvent,
    TransactionPartiallyRefundedEvent,
    TransactionRefundedEvent,
)
from app.modules.transactions.tasks import notify_payment_waitlist_task
from app.modules.users.dto import UserDto
from app.modules.users.events import CabinetUserRegisteredEvent, TelegramUserRegisteredEvent
from app.worker.subscribers import register_all_subscribers

_USER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
_TARGET = UserDto(id=2, login="target", name="target", role=Role.ADMIN, language=Locale.EN)

# One instance per event with a registered handler, built from the real event
# classes so the payload matches what OutboxEventPublisher writes.
_REGISTERED_EVENTS: dict[str, BaseEvent] = {
    event.event_type: event
    for event in [
        OwnerBootstrappedEvent(user=_USER),
        LoginSucceededEvent(user=_USER),
        LoginFailedEvent(login="someone"),
        BootstrapConflictEvent(login="someone"),
        OAuthLoginSucceededEvent(user=_USER, provider=OAuthProvider.GITHUB),
        OAuthLoginFailedEvent(provider=OAuthProvider.GITHUB),
        OAuthIdentityConnectedEvent(user=_USER, provider=OAuthProvider.GITHUB),
        OAuthIdentityDisconnectedEvent(user=_USER, provider=OAuthProvider.GITHUB),
        SessionTheftDetectedEvent(user_id=1, session_id=1),
        SessionRevokedEvent(user=_USER, session_id=1),
        UserSessionRevokedByAdminEvent(actor=_USER, target=_TARGET, session_id=1),
        SubscriptionPurchasedEvent(user=_USER, subscription_id=1, plan_id=1, purchase_type="NEW"),
        SubscriptionRenewedEvent(user=_USER, subscription_id=1, duration_days=30),
        SubscriptionChangedEvent(
            user=_USER, subscription_id=2, previous_subscription_id=1, previous_plan_snapshot={}
        ),
        TransactionRefundedEvent(
            order_id=1,
            user_id=1,
            payment_key="k",
            gateway_type="YOOKASSA",
            amount="10.00",
            currency="USD",
        ),
        TransactionPartiallyRefundedEvent(
            order_id=1, user_id=1, gateway_type="YOOKASSA", amount="5.00", currency="USD"
        ),
        PaidOrderNotFulfilledEvent(
            order_id=1,
            user_id=1,
            payment_key="key-1",
            gateway_type="YOOKASSA",
            amount="5.00",
            currency="USD",
        ),
        TransactionCanceledEvent(order_id=1, user_id=1),
        TransactionExpiredEvent(order_id=1, user_id=1),
        SubscriptionExpiringEvent(user=_USER, subscription_id=1, hours=72),
        SubscriptionExpiredEvent(user=_USER, subscription_id=1),
        SubscriptionTrafficLimitedEvent(user=_USER, subscription_id=1),
        SubscriptionTrafficThresholdEvent(user=_USER, subscription_id=1),
        CabinetNewDeviceSignInEvent(user=_USER, browser="Firefox on Linux"),
        SubscriptionAddOnGrantedEvent(
            user=_USER, target=_TARGET, subscription_id=1, addon_id=1, amount=10
        ),
        SubscriptionGrantedEvent(
            actor=_USER, target=_TARGET, subscription_id=1, plan_id=1, duration_days=30
        ),
        ReferralRewardIssuedEvent(
            user=_USER, level=1, reward_type=ReferralRewardType.EXTRA_DAYS, amount="7"
        ),
        InviteeRewardIssuedEvent(user=_USER, reward_type=ReferralRewardType.EXTRA_DAYS, amount=7),
        AccessSettingsChangedEvent(actor=_USER, payments_reenabled=True),
        AccountsMergedEvent(actor=_USER, target=_TARGET, source=_USER, choices={"name": "target"}),
        PromocodeDiscountExpiringEvent(
            user=_USER, promocode_id=1, code="SALE", percent=10, hours=24
        ),
        SubscriptionExpiredAgoEvent(user=_USER, subscription_id=1, hours=24),
        SubscriptionNotConnectedEvent(user=_USER, subscription_id=1, hours=24),
        TorrentBlockerReportEvent(
            user=_USER, subscription_id=1, node_name="n", destination="d", blocked_until="t"
        ),
        TelegramUserRegisteredEvent(user=_USER, ad_link_code="yt", referral_code="AB12CD34"),
        CabinetUserRegisteredEvent(
            user=_USER, method=CabinetSignInMethod.EMAIL, ad_link_code="yt", referral_code="AB"
        ),
    ]
}


@dataclass(frozen=True, kw_only=True)
class _ProbeEvent(BaseEvent):
    category: ClassVar[EventCategory] = EventCategory.AUTH


def _stored_probe_event(**overrides: Any) -> StoredEvent:
    defaults: dict[str, Any] = {
        "outbox_id": 1,
        "category": EventCategory.AUTH,
        "event_type": "_ProbeEvent",
        "occurred_at": datetime.now(timezone.utc),
        "payload": {},
        "actor_id": None,
        "actor_login": None,
        "actor_name": None,
        "actor_email": None,
        "ip_address": None,
    }
    defaults.update(overrides)
    return StoredEvent(**defaults)


async def test_dispatch_stored_delivers_to_the_subscribed_handler() -> None:
    bus = EventBus()
    received: list[StoredEvent] = []

    async def handler(event: _ProbeEvent, entry: StoredEvent) -> None:
        received.append(entry)

    bus.subscribe(_ProbeEvent, handler)
    await bus.dispatch_stored(_stored_probe_event())

    assert len(received) == 1


async def test_dispatch_stored_ignores_unrelated_event_types() -> None:
    bus = EventBus()
    received: list[StoredEvent] = []

    async def handler(event: _ProbeEvent, entry: StoredEvent) -> None:
        received.append(entry)

    bus.subscribe(_ProbeEvent, handler)
    await bus.dispatch_stored(_stored_probe_event(event_type="_OtherEvent"))

    assert received == []


async def test_one_failing_handler_does_not_stop_another() -> None:
    bus = EventBus()
    received: list[StoredEvent] = []

    async def failing_handler(event: _ProbeEvent, entry: StoredEvent) -> None:
        raise RuntimeError("boom")

    async def working_handler(event: _ProbeEvent, entry: StoredEvent) -> None:
        received.append(entry)

    bus.subscribe(_ProbeEvent, failing_handler)
    bus.subscribe(_ProbeEvent, working_handler)
    error_message = await bus.dispatch_stored(_stored_probe_event())

    assert len(received) == 1
    assert error_message == "boom"


async def test_dispatch_stored_returns_none_when_every_handler_succeeds() -> None:
    bus = EventBus()

    async def handler(event: _ProbeEvent, entry: StoredEvent) -> None:
        pass

    bus.subscribe(_ProbeEvent, handler)
    error_message = await bus.dispatch_stored(_stored_probe_event())

    assert error_message is None


async def test_shutdown_clears_handlers() -> None:
    bus = EventBus()

    async def handler(event: _ProbeEvent, entry: StoredEvent) -> None:
        pass

    bus.subscribe(_ProbeEvent, handler)
    await bus.shutdown()

    assert bus._handlers == {}


def test_register_all_subscribers_registers_auth_handlers() -> None:
    bus = EventBus()
    register_all_subscribers(bus)

    assert "LoginFailedEvent" in bus._handlers


def test_every_typed_subscription_has_a_sample_event() -> None:
    bus = EventBus()
    register_all_subscribers(bus)
    # subscribe() wraps the handler; subscribe_stored() handlers read the raw row
    typed = {
        event_type
        for event_type, handlers in bus._handlers.items()
        if any(hasattr(handler, "__wrapped__") for handler in handlers)
    }

    assert typed - set(_REGISTERED_EVENTS) == set()


@pytest.mark.parametrize("event_type", list(_REGISTERED_EVENTS), ids=list(_REGISTERED_EVENTS))
async def test_registered_handler_reads_its_real_payload_shape(
    event_type: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Handlers read entry.payload[...], and a wrong key would only show up as
    # a logged exception or a task that never fires. .kiq() is stubbed.
    async def _noop_kiq(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(assign_referral_rewards_task, "kiq", _noop_kiq)
    monkeypatch.setattr(reverse_referral_rewards_task, "kiq", _noop_kiq)
    monkeypatch.setattr(recalculate_loyalty_discounts_task, "kiq", _noop_kiq)
    monkeypatch.setattr(deliver_notification_task, "kiq", _noop_kiq)
    monkeypatch.setattr(notify_customer_task, "kiq", _noop_kiq)
    monkeypatch.setattr(show_payment_canceled_task, "kiq", _noop_kiq)
    monkeypatch.setattr(attach_referral_on_registration_task, "kiq", _noop_kiq)
    monkeypatch.setattr(record_ad_link_attribution_task, "kiq", _noop_kiq)
    monkeypatch.setattr(notify_payment_waitlist_task, "kiq", _noop_kiq)

    bus = EventBus()
    register_all_subscribers(bus)
    event = _REGISTERED_EVENTS[event_type]
    stored = StoredEvent(
        outbox_id=1,
        category=event.category,
        event_type=event_type,
        occurred_at=event.occurred_at,
        payload=_build_payload(event),
        actor_id=None,
        actor_login=None,
        actor_name=None,
        actor_email=None,
        ip_address=None,
    )

    assert await bus.dispatch_stored(stored) is None


async def test_subscription_purchased_handler_kicks_referral_rewards_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _capture_kiq(*args: Any, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(assign_referral_rewards_task, "kiq", _capture_kiq)

    bus = EventBus()
    register_all_subscribers(bus)
    event = SubscriptionPurchasedEvent(
        user=_USER, subscription_id=42, plan_id=1, purchase_type="NEW", payment_key="order-1"
    )
    stored = _stored_probe_event(
        category=event.category, event_type=event.event_type, payload=_build_payload(event)
    )

    await bus.dispatch_stored(stored)

    assert calls == [
        {
            "user_id": _USER.id,
            "subscription_id": 42,
            "is_new_purchase": True,
            "payment_key": "order-1",
        }
    ]


async def test_subscription_renewed_handler_kicks_referral_rewards_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _capture_kiq(*args: Any, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(assign_referral_rewards_task, "kiq", _capture_kiq)

    bus = EventBus()
    register_all_subscribers(bus)
    event = SubscriptionRenewedEvent(
        user=_USER, subscription_id=42, duration_days=30, payment_key="order-2"
    )
    stored = _stored_probe_event(
        category=event.category, event_type=event.event_type, payload=_build_payload(event)
    )

    await bus.dispatch_stored(stored)

    assert calls == [
        {
            "user_id": _USER.id,
            "subscription_id": 42,
            "is_new_purchase": False,
            "payment_key": "order-2",
        }
    ]


async def test_subscription_changed_handler_kicks_referral_rewards_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _capture_kiq(*args: Any, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(assign_referral_rewards_task, "kiq", _capture_kiq)

    bus = EventBus()
    register_all_subscribers(bus)
    event = SubscriptionChangedEvent(
        user=_USER,
        subscription_id=43,
        previous_subscription_id=42,
        previous_plan_snapshot={},
        payment_key="order-3",
    )
    stored = _stored_probe_event(
        category=event.category, event_type=event.event_type, payload=_build_payload(event)
    )

    await bus.dispatch_stored(stored)

    assert calls == [
        {
            "user_id": _USER.id,
            "subscription_id": 43,
            "is_new_purchase": False,
            "payment_key": "order-3",
        }
    ]


async def test_unpaid_subscription_events_do_not_kick_referral_rewards_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # promocode, referral and trial grants carry no payment_key
    calls: list[dict[str, Any]] = []

    async def _capture_kiq(*args: Any, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(assign_referral_rewards_task, "kiq", _capture_kiq)

    bus = EventBus()
    register_all_subscribers(bus)
    for event in (
        SubscriptionPurchasedEvent(user=_USER, subscription_id=42, plan_id=1, purchase_type="NEW"),
        SubscriptionRenewedEvent(user=_USER, subscription_id=42, duration_days=30),
    ):
        stored = _stored_probe_event(
            category=event.category, event_type=event.event_type, payload=_build_payload(event)
        )
        await bus.dispatch_stored(stored)

    assert calls == []

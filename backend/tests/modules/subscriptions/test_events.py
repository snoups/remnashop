from dataclasses import fields

from app.core.enums import Locale, Role
from app.core.events import EventCategory
from app.modules.subscriptions.events import (
    SubscriptionAddOnGrantedEvent,
    SubscriptionChangedEvent,
    SubscriptionPurchasedEvent,
    SubscriptionRenewedEvent,
)
from app.modules.users.dto import UserDto


def _user() -> UserDto:
    return UserDto(id=1, name="Buyer", role=Role.USER, language=Locale.EN)


def test_subscription_purchased_event_category_and_fields() -> None:
    event = SubscriptionPurchasedEvent(
        user=_user(), subscription_id=1, plan_id=2, purchase_type="NEW"
    )
    assert event.category == EventCategory.SUBSCRIPTION
    assert event.event_type == "SubscriptionPurchasedEvent"


def test_subscription_renewed_event_carries_subscription_id() -> None:
    event = SubscriptionRenewedEvent(user=_user(), subscription_id=1, duration_days=30)
    assert event.subscription_id == 1
    assert event.duration_days == 30


def test_subscription_changed_event_carries_previous_snapshot() -> None:
    event = SubscriptionChangedEvent(
        user=_user(),
        subscription_id=1,
        previous_subscription_id=0,
        previous_plan_snapshot={"plan_id": 1},
    )
    assert event.previous_plan_snapshot == {"plan_id": 1}
    assert {f.name for f in fields(event)} >= {
        "subscription_id",
        "previous_plan_snapshot",
    }


def test_subscription_changed_event_carries_previous_subscription_id() -> None:
    event = SubscriptionChangedEvent(
        user=_user(),
        subscription_id=2,
        previous_subscription_id=1,
        previous_plan_snapshot={"plan_id": 1},
    )

    assert event.subscription_id == 2
    assert event.previous_subscription_id == 1


def test_subscription_addon_granted_event_carries_addon_id() -> None:
    event = SubscriptionAddOnGrantedEvent(
        user=_user(), target=_user(), subscription_id=1, addon_id=3, amount=10
    )
    assert event.addon_id == 3
    assert event.amount == 10

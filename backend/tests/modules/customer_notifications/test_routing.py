from typing import Optional

import pytest

from app.modules.customer_notifications.routing import (
    CustomerChannel,
    channels_for,
    should_notify_customer,
)
from app.modules.transactions import RecurringReason

T, E = CustomerChannel.TELEGRAM, CustomerChannel.EMAIL


@pytest.mark.parametrize(
    ("event_type", "telegram_id", "email", "expected"),
    [
        ("SubscriptionExpiringEvent", 1, "a@b.c", [T]),
        ("SubscriptionExpiringEvent", None, "a@b.c", [E]),
        ("SubscriptionExpiringEvent", 1, None, [T]),
        ("SubscriptionExpiringEvent", None, None, []),
        ("SubscriptionPurchasedEvent", 1, "a@b.c", [T, E]),
        ("SubscriptionPurchasedEvent", None, "a@b.c", [E]),
        ("TransactionRefundedEvent", 1, None, [T]),
        ("CabinetNewDeviceSignInEvent", 1, "a@b.c", [T, E]),
        ("AccountsMergedEvent", 1, "a@b.c", [T, E]),
        ("ReferralRewardIssuedEvent", 1, "a@b.c", [T]),
    ],
)
def test_channels(
    event_type: str,
    telegram_id: Optional[int],
    email: Optional[str],
    expected: list[CustomerChannel],
) -> None:
    assert channels_for(event_type, telegram_id=telegram_id, email=email) == expected


@pytest.mark.parametrize("reason", list(RecurringReason))
@pytest.mark.parametrize(
    "event_type",
    [
        "RecurringPaymentFailedEvent",
        "RecurringPaymentPausedEvent",
        "RecurringPaymentExhaustedEvent",
    ],
)
def test_recurring_customer_notifications_follow_the_reason_policy(reason, event_type):
    assert (
        should_notify_customer(event_type, {"reason": reason.value})
        is reason.policy.customer_notice
    )

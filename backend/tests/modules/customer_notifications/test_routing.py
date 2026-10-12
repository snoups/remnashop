from typing import Optional

import pytest

from app.modules.customer_notifications.routing import CustomerChannel, channels_for

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

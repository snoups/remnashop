from typing import Mapping, Optional, Union

import pytest

from app.modules.customer_notifications.links import customer_url

_SUB = ("Purchased", "Renewed", "Changed", "AddOnGranted", "Granted")
_RENEW = ("Expiring", "Expired", "ExpiredAgo", "TrafficLimited", "TrafficThreshold")
_ORDER = {"order_id": 42}


@pytest.mark.parametrize(
    ("event_type", "subscription_id", "args", "expected"),
    [
        *[(f"Subscription{n}Event", 7, {}, "/?sub=7") for n in _SUB],
        ("TorrentBlockerReportEvent", 7, {}, "/?sub=7"),
        ("SubscriptionPurchasedEvent", None, {}, "/"),
        *[(f"Subscription{n}Event", 7, {}, "/?sub=7&renew=1") for n in _RENEW],
        ("SubscriptionExpiringEvent", None, {}, "/"),
        ("TransactionRefundedEvent", None, _ORDER, "/profile/payments?id=42"),
        ("TransactionPartiallyRefundedEvent", None, _ORDER, "/profile/payments?id=42"),
        ("TransactionRefundedEvent", None, {}, "/profile/payments"),
        ("PaidOrderNotFulfilledEvent", None, _ORDER, "/profile/payments?id=42&support=1"),
        ("SubscriptionNotConnectedEvent", 7, {}, "/subscription/7/connect"),
        ("CabinetNewDeviceSignInEvent", None, {}, "/profile?signout=others"),
        ("AccountsMergedEvent", None, {}, "/profile?support=1"),
        ("ReferralRewardIssuedEvent", None, {}, "/invite/friends"),
        ("InviteeRewardIssuedEvent", None, {}, "/profile"),
        ("PromocodeDiscountExpiringEvent", None, {}, "/purchase"),
        ("PaymentsRestored", None, {}, "/purchase"),
        ("SomethingUnknownEvent", 7, {}, "/"),
    ],
)
def test_customer_url(
    event_type: str,
    subscription_id: Optional[int],
    args: Mapping[str, Union[str, int]],
    expected: str,
) -> None:
    assert customer_url(event_type, subscription_id, args) == expected

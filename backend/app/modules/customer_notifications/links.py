from typing import Any, Final, Mapping, Optional

from app.modules.account_merge import AccountsMergedEvent
from app.modules.cabinet_auth import CabinetNewDeviceSignInEvent
from app.modules.customer_notifications.waitlist import PAYMENTS_RESTORED
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
    TransactionPartiallyRefundedEvent,
    TransactionRefundedEvent,
)

# where a push or a feed item takes the customer, relative to the cabinet
_FIXED: Final[dict[str, str]] = {
    CabinetNewDeviceSignInEvent.__name__: "/profile?signout=others",
    AccountsMergedEvent.__name__: "/profile?support=1",
    ReferralRewardIssuedEvent.__name__: "/invite/friends",
    InviteeRewardIssuedEvent.__name__: "/profile",
    PromocodeDiscountExpiringEvent.__name__: "/purchase",
    PAYMENTS_RESTORED: "/purchase",
}
_SUBSCRIPTION: Final[frozenset[str]] = frozenset(
    e.__name__
    for e in (
        SubscriptionPurchasedEvent,
        SubscriptionRenewedEvent,
        SubscriptionChangedEvent,
        SubscriptionAddOnGrantedEvent,
        SubscriptionGrantedEvent,
        TorrentBlockerReportEvent,
    )
)
_RENEW: Final[frozenset[str]] = frozenset(
    e.__name__
    for e in (
        SubscriptionExpiringEvent,
        SubscriptionExpiredEvent,
        SubscriptionExpiredAgoEvent,
        SubscriptionTrafficLimitedEvent,
        SubscriptionTrafficThresholdEvent,
    )
)
_REFUNDS: Final[frozenset[str]] = frozenset(
    e.__name__ for e in (TransactionRefundedEvent, TransactionPartiallyRefundedEvent)
)


def customer_url(event_type: str, subscription_id: Optional[int], args: Mapping[str, Any]) -> str:
    if event_type in _FIXED:
        return _FIXED[event_type]
    if event_type == SubscriptionNotConnectedEvent.__name__ and subscription_id is not None:
        return f"/subscription/{subscription_id}/connect"
    if event_type in _SUBSCRIPTION and subscription_id is not None:
        return f"/?sub={subscription_id}"
    if event_type in _RENEW and subscription_id is not None:
        return f"/?sub={subscription_id}&renew=1"
    if event_type in _REFUNDS or event_type == PaidOrderNotFulfilledEvent.__name__:
        order_id = args.get("order_id")
        if order_id is None:
            return "/profile/payments"
        support = "&support=1" if event_type == PaidOrderNotFulfilledEvent.__name__ else ""
        return f"/profile/payments?id={order_id}{support}"
    return "/"

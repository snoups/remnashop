from enum import auto
from typing import Final, Optional

from app.core.enums import UpperStrEnum
from app.modules.account_merge import AccountsMergedEvent
from app.modules.cabinet_auth import CabinetNewDeviceSignInEvent
from app.modules.subscriptions import (
    SubscriptionAddOnGrantedEvent,
    SubscriptionChangedEvent,
    SubscriptionGrantedEvent,
    SubscriptionPurchasedEvent,
    SubscriptionRenewedEvent,
)
from app.modules.transactions import (
    PaidOrderNotFulfilledEvent,
    TransactionPartiallyRefundedEvent,
    TransactionRefundedEvent,
)


class CustomerChannel(UpperStrEnum):
    TELEGRAM = auto()
    EMAIL = auto()
    # added by NotifyCustomerUseCase on top of these routes, never by channels_for
    PUSH = auto()


# money and account security: worth a receipt by email even when the bot delivered it
ALWAYS_BOTH: Final[frozenset[str]] = frozenset(
    event.__name__
    for event in (
        SubscriptionPurchasedEvent,
        SubscriptionRenewedEvent,
        SubscriptionChangedEvent,
        SubscriptionAddOnGrantedEvent,
        SubscriptionGrantedEvent,
        TransactionRefundedEvent,
        TransactionPartiallyRefundedEvent,
        PaidOrderNotFulfilledEvent,
        CabinetNewDeviceSignInEvent,
        AccountsMergedEvent,
    )
)


def channels_for(
    event_type: str, *, telegram_id: Optional[int], email: Optional[str]
) -> list[CustomerChannel]:
    if event_type in ALWAYS_BOTH:
        return [
            channel
            for channel, present in (
                (CustomerChannel.TELEGRAM, telegram_id),
                (CustomerChannel.EMAIL, email),
            )
            if present
        ]
    if telegram_id is not None:
        return [CustomerChannel.TELEGRAM]
    return [CustomerChannel.EMAIL] if email else []

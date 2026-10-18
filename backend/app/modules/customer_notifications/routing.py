from enum import auto
from typing import Final, Optional

from app.core.enums import UpperStrEnum


class CustomerChannel(UpperStrEnum):
    TELEGRAM = auto()
    EMAIL = auto()


# money and account security: worth a receipt by email even when the bot delivered it
ALWAYS_BOTH: Final[frozenset[str]] = frozenset(
    {
        "SubscriptionPurchasedEvent",
        "SubscriptionRenewedEvent",
        "SubscriptionChangedEvent",
        "SubscriptionAddOnGrantedEvent",
        "SubscriptionGrantedEvent",
        "TransactionRefundedEvent",
        "TransactionPartiallyRefundedEvent",
        "PaidOrderNotFulfilledEvent",
        "CabinetNewDeviceSignInEvent",
        "AccountsMergedEvent",
    }
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

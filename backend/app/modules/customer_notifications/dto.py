from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final, Optional, Union


@dataclass(frozen=True, kw_only=True)
class NotifyCustomerDto:
    user_id: int
    event_type: str
    outbox_id: int
    args: dict[str, Union[str, int]]
    payment_key: Optional[str] = None
    subscription_id: Optional[int] = None
    # Telegram refused this notification for good: the rest goes out by email
    telegram_refused: bool = False


@dataclass(frozen=True, kw_only=True)
class SendCustomerTelegramDto:
    user_id: int
    text: str
    # one {text, callback_data} button per row
    buttons: list[dict[str, str]] = field(default_factory=list)
    # requeued with telegram_refused when Telegram refuses the message
    notification: Optional[NotifyCustomerDto] = None
    # built by telegram_card; a message queued before that went out as plain text
    html: bool = False


@dataclass(frozen=True, kw_only=True)
class ShowPaymentCanceledDto:
    order_id: int


FEED_LIMIT: Final = 50
FEED_RETENTION: Final = timedelta(days=90)


@dataclass(frozen=True, kw_only=True)
class CustomerNotificationDto:
    id: int
    event_type: str
    args: dict[str, Any]
    subscription_id: Optional[int]
    created_at: datetime
    read_at: Optional[datetime]


@dataclass(frozen=True, kw_only=True)
class CustomerFeedItemDto:
    id: int
    event_type: str
    title: str
    body: str
    url: str
    created_at: datetime
    read: bool


@dataclass(frozen=True, kw_only=True)
class CustomerFeedDto:
    items: list[CustomerFeedItemDto]
    unread_count: int

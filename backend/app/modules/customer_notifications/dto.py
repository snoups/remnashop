from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass(frozen=True, kw_only=True)
class NotifyCustomerDto:
    user_id: int
    event_type: str
    outbox_id: int
    args: dict[str, Union[str, int]]
    payment_key: Optional[str] = None
    subscription_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class SendCustomerTelegramDto:
    user_id: int
    text: str
    # one {text, callback_data} button per row
    buttons: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class ShowPaymentCanceledDto:
    order_id: int

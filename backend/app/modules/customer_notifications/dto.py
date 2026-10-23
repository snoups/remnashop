from dataclasses import dataclass
from typing import Optional, Union


@dataclass(frozen=True, kw_only=True)
class NotifyCustomerDto:
    user_id: int
    event_type: str
    outbox_id: int
    args: dict[str, Union[str, int]]
    payment_key: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class SendCustomerTelegramDto:
    user_id: int
    text: str


@dataclass(frozen=True, kw_only=True)
class ShowPaymentCanceledDto:
    order_id: int

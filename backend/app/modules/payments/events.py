from dataclasses import dataclass
from typing import ClassVar

from app.core.events import EventCategory, SystemEvent


@dataclass(frozen=True, kw_only=True)
class PaymentOrderRefundedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    user_id: int
    gateway_type: str
    amount: str
    currency: str

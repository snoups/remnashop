from dataclasses import dataclass
from typing import ClassVar

from app.core.events import ActorEvent, ActorTargetEvent, EventCategory, SystemEvent


@dataclass(frozen=True, kw_only=True)
class TransactionRefundedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    user_id: int
    payment_key: str
    gateway_type: str
    amount: str
    currency: str


@dataclass(frozen=True, kw_only=True)
class TransactionPartiallyRefundedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    user_id: int
    gateway_type: str
    amount: str
    currency: str


@dataclass(frozen=True, kw_only=True)
class TransactionFulfilledManuallyEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    previous_status: str


@dataclass(frozen=True, kw_only=True)
class TransactionRefundedManuallyEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    rollback_subscription: bool


@dataclass(frozen=True, kw_only=True)
class GatewayTestPaymentCreatedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    gateway_type: str

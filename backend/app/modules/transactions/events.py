from dataclasses import dataclass
from typing import ClassVar, Optional

from app.core.enums import Currency, PaymentGatewayType, TransactionStatus
from app.core.events import ActorEvent, ActorTargetEvent, EventCategory, SystemEvent, UserEvent


@dataclass(frozen=True, kw_only=True)
class TransactionRefundedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    user_id: int
    payment_key: str
    gateway_type: PaymentGatewayType
    amount: str
    currency: Currency


@dataclass(frozen=True, kw_only=True)
class TransactionPartiallyRefundedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    user_id: int
    gateway_type: PaymentGatewayType
    amount: str
    currency: Currency


@dataclass(frozen=True, kw_only=True)
class PaidOrderNotFulfilledEvent(SystemEvent):
    """Paid, past the grace period, and still no subscription; the sweep keeps retrying."""

    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    user_id: int
    payment_key: str
    gateway_type: PaymentGatewayType
    amount: str
    currency: Currency


@dataclass(frozen=True, kw_only=True)
class TransactionFulfilledManuallyEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    previous_status: TransactionStatus


@dataclass(frozen=True, kw_only=True)
class TransactionPaymentConfirmedEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    previous_status: TransactionStatus
    gateway_type: PaymentGatewayType


@dataclass(frozen=True, kw_only=True)
class TransactionRefundedManuallyEvent(ActorTargetEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    rollback_subscription: bool


@dataclass(frozen=True, kw_only=True)
class GatewayTestPaymentCreatedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    gateway_type: PaymentGatewayType


@dataclass(frozen=True, kw_only=True)
class CheckoutCreatedEvent(UserEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    gateway_type: PaymentGatewayType
    amount: str
    currency: Currency
    # the unpaid order this one canceled in its place
    replaced_order_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class TransactionExpiredEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    user_id: int


@dataclass(frozen=True, kw_only=True)
class TransactionCanceledEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    order_id: int
    user_id: int


@dataclass(frozen=True, kw_only=True)
class UnratedAnchorAmountsRatedEvent(ActorEvent):
    category: ClassVar[EventCategory] = EventCategory.PRICING
    currencies: list[Currency]
    count: int

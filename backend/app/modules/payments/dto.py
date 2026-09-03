from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Optional

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
)
from app.modules.subscriptions import PlanSnapshot

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200


@dataclass(frozen=True, kw_only=True)
class PriceQuote:
    base_price: Decimal
    discount_percent: int
    discount_source: DiscountSource
    final_price: Decimal


class PaymentOrderDto(BaseDto, TimestampMixin):
    user_id: int
    plan_id: Optional[int]
    plan_snapshot: PlanSnapshot
    duration_days: int
    currency: Currency
    purchase_type: PurchaseType
    target_subscription_id: Optional[int] = None
    gateway_type: PaymentGatewayType
    external_payment_id: Optional[str] = None
    status: PaymentOrderStatus = PaymentOrderStatus.PENDING
    base_price: Decimal
    discount_percent: int = 0
    discount_source: DiscountSource = DiscountSource.NONE
    final_price: Decimal
    customer_email: Optional[str] = None
    idempotency_key: str
    expires_at: datetime


@dataclass(frozen=True, kw_only=True)
class CreatePaymentOrderDto:
    user_id: int
    plan_id: int
    plan_snapshot: PlanSnapshot
    duration_days: int
    currency: Currency
    purchase_type: PurchaseType
    target_subscription_id: Optional[int]
    gateway_type: PaymentGatewayType
    base_price: Decimal
    discount_percent: int
    discount_source: DiscountSource
    final_price: Decimal
    customer_email: Optional[str]
    idempotency_key: str
    expires_at: datetime


@dataclass(frozen=True, kw_only=True)
class CreateCheckoutDto:
    user_id: int
    plan_id: int
    duration_days: int
    currency: Currency
    purchase_type: PurchaseType
    gateway_type: PaymentGatewayType
    target_subscription_id: Optional[int] = None
    customer_email: Optional[str] = None


class CheckoutResultDto(BaseDto):
    order_id: int
    confirmation_url: Optional[str] = None

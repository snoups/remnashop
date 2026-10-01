from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Optional

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseType,
    TransactionStatus,
)
from app.modules.subscriptions import PlanSnapshot
from app.modules.users import UserDto

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200


@dataclass(frozen=True, kw_only=True)
class PriceQuote:
    base_price: Decimal
    discount_percent: int
    discount_source: DiscountSource
    final_price: Decimal
    discount_promocode_id: Optional[int] = None


class TransactionDto(BaseDto, TimestampMixin):
    user_id: int
    plan_id: Optional[int]
    plan_snapshot: PlanSnapshot
    duration_days: int
    currency: Currency
    purchase_type: PurchaseType
    target_subscription_id: Optional[int] = None
    gateway_type: PaymentGatewayType
    external_payment_id: Optional[str] = None
    status: TransactionStatus = TransactionStatus.PENDING
    base_price: Decimal
    discount_percent: int = 0
    discount_source: DiscountSource = DiscountSource.NONE
    final_price: Decimal
    discount_promocode_id: Optional[int] = None
    customer_email: Optional[str] = None
    idempotency_key: str
    expires_at: datetime
    is_test: bool = False


@dataclass(frozen=True, kw_only=True)
class TransactionWithUserDto:
    order: TransactionDto
    user: Optional[UserDto]


@dataclass(frozen=True, kw_only=True)
class CreateTransactionDto:
    user_id: int
    plan_id: Optional[int]
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
    discount_promocode_id: Optional[int] = None
    idempotency_key: str
    expires_at: datetime
    is_test: bool = False


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
    # required for a LINK plan: the link's code is what grants access to it
    plan_code: Optional[str] = None


class CheckoutResultDto(BaseDto):
    order_id: int
    confirmation_url: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class TestPaymentDto:
    order_id: int
    confirmation_url: Optional[str]


@dataclass(frozen=True, kw_only=True)
class TransactionSummaryDto:
    report_currency: Currency
    total_count: int
    pending_count: int
    paid_count: int
    conversion_rate: Decimal
    revenue: Decimal
    average_check: Optional[Decimal]
    average_discount: Optional[Decimal]
    # paid orders' base price minus what was actually paid, in report_currency
    discount_amount: Decimal
    refunded_amount: Decimal

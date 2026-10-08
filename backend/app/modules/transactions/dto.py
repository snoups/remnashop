from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Final, Optional

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

if TYPE_CHECKING:
    # gateways.base imports TransactionDto from here
    from app.modules.transactions.gateways.base import WebhookRequest

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200
# time for the normal dispatch + worker run to finish before an order counts as stuck
_GRACE_PERIOD: Final[timedelta] = timedelta(minutes=10)


@dataclass(frozen=True, kw_only=True)
class PriceQuote:
    base_price: Decimal
    discount_percent: int
    discount_source: DiscountSource
    final_price: Decimal
    anchor_base_price: Decimal
    anchor_final_price: Decimal
    discount_promocode_id: Optional[int] = None
    plan_discount_percent: int = 0


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
    plan_discount_percent: int = 0
    final_price: Decimal
    anchor_base_price: Decimal
    anchor_final_price: Decimal
    discount_promocode_id: Optional[int] = None
    customer_email: Optional[str] = None
    idempotency_key: str
    expires_at: datetime
    fulfilled_at: Optional[datetime] = None
    fulfilled_subscription_id: Optional[int] = None
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
    plan_discount_percent: int = 0
    final_price: Decimal
    anchor_base_price: Decimal
    anchor_final_price: Decimal
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


@dataclass(frozen=True, kw_only=True)
class GetTransactionSummaryDto:
    status: Optional[TransactionStatus] = None
    gateway_type: Optional[PaymentGatewayType] = None
    purchase_type: Optional[PurchaseType] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    search: Optional[str] = None
    user_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class HandleWebhookDto:
    gateway_type: PaymentGatewayType
    request: "WebhookRequest"


@dataclass(frozen=True, kw_only=True)
class ListTransactionsDto:
    status: Optional[TransactionStatus] = None
    gateway_type: Optional[PaymentGatewayType] = None
    purchase_type: Optional[PurchaseType] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    search: Optional[str] = None
    user_id: Optional[int] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class ReconcilePaidTransactionsDto:
    grace_period: timedelta = _GRACE_PERIOD


@dataclass(frozen=True, kw_only=True)
class PaidTransactionDto:
    user_id: int
    paid_at: datetime
    currency: Currency
    final_price: Decimal
    anchor_final_price: Decimal
    anchor_base_price: Decimal
    discount_percent: int
    plan_discount_percent: int
    discount_promocode_id: Optional[int]
    purchase_type: PurchaseType
    plan_id: Optional[int]
    plan_name: str
    duration_days: int
    gateway_type: PaymentGatewayType

    @property
    def user_discount_amount(self) -> Decimal:
        # the user's own discount only, on top of the plan's
        after_plan = self.anchor_base_price * (100 - self.plan_discount_percent) / 100
        return after_plan - self.anchor_final_price


@dataclass(frozen=True, kw_only=True)
class PaymentAttemptDto:
    gateway_type: PaymentGatewayType
    status: TransactionStatus
    anchor_final_price: Decimal


@dataclass(frozen=True, kw_only=True)
class PaymentWaitlistCountDto:
    total: int

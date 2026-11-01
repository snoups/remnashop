from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final, Literal, Optional

from app.core.constants import DEFAULT_PAGE_SIZE
from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import (
    Currency,
    DiscountSource,
    Locale,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from app.modules.subscriptions import PlanSnapshot, RollbackPreviewDto
from app.modules.users import UserDto

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


@dataclass(frozen=True, kw_only=True)
class PaymentMethodDto:
    gateway_type: PaymentGatewayType
    currency: Currency
    requires_email: bool = False


class TransactionDto(BaseDto, TimestampMixin):
    user_id: int
    plan_id: Optional[int]
    plan_snapshot: PlanSnapshot
    duration_days: int
    currency: Currency
    purchase_type: PurchaseType
    channel: PurchaseChannel
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
    discount_from_promocode: bool = False
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
    channel: PurchaseChannel
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
    discount_from_promocode: bool = False
    idempotency_key: str
    expires_at: datetime
    is_test: bool = False


@dataclass(frozen=True, kw_only=True)
class StarsPreCheckoutDto:
    telegram_id: int
    payload: str
    currency: str
    total_amount: int


@dataclass(frozen=True, kw_only=True)
class StarsPaymentDto:
    telegram_id: int
    payload: str
    currency: str
    total_amount: int
    charge_id: str


@dataclass(frozen=True, kw_only=True)
class CreateCheckoutDto:
    plan_id: int
    duration_days: int
    currency: Currency
    purchase_type: PurchaseType
    channel: PurchaseChannel
    gateway_type: PaymentGatewayType
    target_subscription_id: Optional[int] = None
    customer_email: Optional[str] = None
    # required for a LINK plan: the link's code is what grants access to it
    plan_code: Optional[str] = None
    return_to: Literal["default", "cabinet"] = "default"
    legal_locale: Optional[Locale] = None
    client_ip: Optional[str] = None
    # the total the customer was shown; None skips the check
    expected_price: Optional[Decimal] = None


@dataclass(frozen=True, kw_only=True)
class QuoteCheckoutDto:
    plan_id: int
    duration_days: int
    currency: Currency
    plan_code: Optional[str] = None
    renew_subscription_id: Optional[int] = None


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
class WebhookRequest:
    body: bytes
    headers: dict[str, str]
    client_ip: str = ""


@dataclass(frozen=True, kw_only=True)
class HandleWebhookDto:
    gateway_type: PaymentGatewayType
    request: WebhookRequest


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
class ListOwnTransactionsDto:
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


@dataclass(frozen=True, kw_only=True)
class ReconcilePaidTransactionsDto:
    grace_period: timedelta = _GRACE_PERIOD


@dataclass(frozen=True, kw_only=True)
class MarkOrderFulfilledDto:
    payment_key: str
    subscription_id: int


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
    channel: PurchaseChannel

    @property
    def user_discount_amount(self) -> Decimal:
        # the user's own discount only, on top of the plan's
        after_plan = self.anchor_base_price * (100 - self.plan_discount_percent) / 100
        return after_plan - self.anchor_final_price


@dataclass(frozen=True, kw_only=True)
class PaidTotalsDto:
    payments: int
    paying_users: int
    revenue: Decimal  # anchor currency


@dataclass(frozen=True, kw_only=True)
class PayerSummaryDto:
    user_id: int
    payments: int
    renewals: int
    spent: Decimal  # anchor currency
    first_paid_at: datetime
    last_paid_at: datetime
    first_plan_name: str


@dataclass(frozen=True, kw_only=True)
class PaymentAttemptDto:
    gateway_type: PaymentGatewayType
    status: TransactionStatus
    anchor_final_price: Decimal


@dataclass(frozen=True, kw_only=True)
class NotifyPaymentWaitlistDto:
    outbox_id: int


@dataclass(frozen=True, kw_only=True)
class PaymentWaitlistCountDto:
    total: int


@dataclass(frozen=True, kw_only=True)
class RefundTransactionDto:
    transaction_id: int
    rollback_subscription: bool
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class RefundPreviewDto:
    refundable: bool
    reason: Optional[str]
    rollback: Optional[RollbackPreviewDto]


@dataclass(frozen=True, kw_only=True)
class RefundResultDto:
    transaction: TransactionWithUserDto
    rollback_failed: bool

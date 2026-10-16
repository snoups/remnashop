from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.enums import Currency, PaymentGatewayType, PurchaseType, TransactionStatus
from app.modules.subscriptions import PlanSnapshot
from app.modules.transactions.dto import TransactionDto


class CreateCheckoutRequest(BaseModel):
    plan_id: int
    duration_days: int = Field(gt=0)
    currency: Currency
    purchase_type: PurchaseType
    gateway_type: PaymentGatewayType
    target_subscription_id: Optional[int] = None
    customer_email: Optional[EmailStr] = None
    plan_code: Optional[str] = Field(default=None, max_length=64)


class CheckoutResponse(BaseModel):
    order_id: int
    confirmation_url: Optional[str] = None


class TransactionUserResponse(BaseModel):
    name: str
    username: Optional[str]
    telegram_id: Optional[int]
    email: Optional[str]


class TransactionResponse(BaseModel):
    id: int
    user_id: int
    user: Optional[TransactionUserResponse]
    # None once the plan is deleted; plan_snapshot always records what was ordered
    plan_id: Optional[int]
    plan_snapshot: dict[str, Any]
    duration_days: int
    currency: str
    purchase_type: str
    target_subscription_id: Optional[int]
    gateway_type: str
    external_payment_id: Optional[str]
    status: str
    base_price: Decimal
    discount_percent: int
    discount_source: str
    plan_discount_percent: int
    final_price: Decimal
    customer_email: Optional[str]
    idempotency_key: str
    is_test: bool
    expires_at: datetime
    # the subscription the order provisioned, once reconciliation has seen it
    fulfilled_subscription_id: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    @field_validator("plan_snapshot", mode="before")
    @classmethod
    def _snapshot_as_json(cls, value: Any) -> Any:
        return value.to_json() if isinstance(value, PlanSnapshot) else value


class TransactionPageResponse(BaseModel):
    items: list[TransactionResponse]
    total: int


class TransactionSummaryResponse(BaseModel):
    report_currency: Currency
    total_count: int
    pending_count: int
    paid_count: int
    conversion_rate: Decimal
    revenue: Decimal
    average_check: Optional[Decimal]
    average_discount: Optional[Decimal]
    discount_amount: Decimal
    refunded_amount: Decimal


class TransactionGatewayListResponse(BaseModel):
    items: list[PaymentGatewayType]
    total: int


class CreateTestPaymentRequest(BaseModel):
    gateway_type: PaymentGatewayType


class TestPaymentResponse(BaseModel):
    order_id: int
    confirmation_url: Optional[str]


class TestPaymentStatusResponse(BaseModel):
    status: TransactionStatus


class PaymentWaitlistCountResponse(BaseModel):
    total: int


class RollbackPreviewResponse(BaseModel):
    available: bool
    blocked_reason: Optional[str]
    old_term_expired: bool


class RefundPreviewResponse(BaseModel):
    refundable: bool
    reason: Optional[str]
    rollback: Optional[RollbackPreviewResponse]


class RefundTransactionRequest(BaseModel):
    rollback_subscription: bool


class RefundTransactionResponse(BaseModel):
    transaction: TransactionResponse
    rollback_failed: bool


class OwnTransactionResponse(BaseModel):
    id: int
    status: TransactionStatus
    final_price: Decimal
    currency: Currency
    purchase_type: PurchaseType
    gateway_type: PaymentGatewayType
    plan_name: str
    duration_days: int
    created_at: Optional[datetime]

    @classmethod
    def from_dto(cls, order: TransactionDto) -> "OwnTransactionResponse":
        return cls(
            id=order.id,
            status=order.status,
            final_price=order.final_price,
            currency=order.currency,
            purchase_type=order.purchase_type,
            gateway_type=order.gateway_type,
            plan_name=order.plan_snapshot.name,
            duration_days=order.duration_days,
            created_at=order.created_at,
        )


class OwnTransactionListResponse(BaseModel):
    items: list[OwnTransactionResponse]
    total: int
    page: int
    page_size: int


class PaymentMethodResponse(BaseModel):
    gateway_type: PaymentGatewayType
    currency: Currency


class PaymentMethodListResponse(BaseModel):
    items: list[PaymentMethodResponse]
    total: int

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import Currency, PaymentGatewayType, PurchaseType, TransactionStatus


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
    # None once the plan is deleted -- plan_snapshot is the durable record of
    # what was actually ordered, always populated regardless of plan_id.
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
    final_price: Decimal
    customer_email: Optional[str]
    idempotency_key: str
    expires_at: datetime
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


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

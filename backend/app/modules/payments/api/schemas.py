from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import Currency, PaymentGatewayType, PurchaseType


class CreateCheckoutRequest(BaseModel):
    plan_id: int
    duration_days: int = Field(gt=0)
    currency: Currency
    purchase_type: PurchaseType
    gateway_type: PaymentGatewayType
    target_subscription_id: Optional[int] = None
    customer_email: Optional[EmailStr] = None


class CheckoutResponse(BaseModel):
    order_id: int
    confirmation_url: Optional[str] = None


class PaymentOrderResponse(BaseModel):
    id: int
    user_id: int
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


class PaymentOrderPageResponse(BaseModel):
    items: list[PaymentOrderResponse]
    total: int

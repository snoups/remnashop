from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

from src.core.enums import Currency, PaymentGatewayType, PurchaseType


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: dict[str, str]


class TelegramAuthRequest(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


class CreatePaymentRequest(BaseModel):
    telegram_id: int
    plan_id: int
    duration_days: int
    gateway_type: PaymentGatewayType
    purchase_type: PurchaseType = PurchaseType.NEW
    currency: Optional[Currency] = None


class PlanDurationPriceResponse(BaseModel):
    currency: str
    price: str


class PlanDurationResponse(BaseModel):
    id: int
    days: int
    prices: list[PlanDurationPriceResponse]


class PlanResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    type: str
    traffic_limit: int
    device_limit: int
    is_active: bool
    durations: list[PlanDurationResponse]


class SubscriptionResponse(BaseModel):
    id: int
    plan_name: str
    status: str
    traffic_limit: int
    traffic_used: int
    traffic_remaining: int
    traffic_percent: float
    device_limit: int
    created_at: datetime
    expire_at: datetime
    days_remaining: int
    subscription_url: Optional[str] = None


class UserResponse(BaseModel):
    telegram_id: int
    name: str
    username: Optional[str] = None
    language: str
    personal_discount: int = 0
    points: int = 0
    has_subscription: bool = False
    subscription: Optional[SubscriptionResponse] = None


class AuthResponse(BaseModel):
    user: UserResponse
    token: str
    expires_at: datetime
    is_new_user: bool = False


class PaymentResponse(BaseModel):
    payment_id: str
    payment_url: Optional[str] = None
    amount: str
    currency: str
    gateway_type: str
    status: str
    expires_at: Optional[datetime] = None


class PaymentStatusResponse(BaseModel):
    payment_id: str
    status: str
    amount: str
    currency: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    subscription: Optional[dict[str, Any]] = None


class GatewayResponse(BaseModel):
    type: str
    name: str
    currency: str
    is_active: bool


class SettingsResponse(BaseModel):
    default_currency: str
    supported_currencies: list[str]
    telegram_bot_username: str
    support_url: Optional[str] = None

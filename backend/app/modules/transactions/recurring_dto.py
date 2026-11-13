from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


@dataclass(frozen=True, kw_only=True)
class RecurringPaymentDto:
    subscription_id: int
    source_transaction_id: Optional[int]
    payment_method_id: Optional[str] = field(repr=False)
    shop_id: str
    enabled: bool
    customer_disabled: bool
    last_error: Optional[str]
    pending_transaction_id: Optional[int]
    attempted_at: Optional[datetime]


class RecurringPaymentState(BaseModel):
    subscription_id: int
    enabled: bool
    available: bool
    customer_disabled: bool = False
    amount_limit: Optional[Decimal] = None
    currency: Optional[str] = None
    duration_days: Optional[int] = None
    next_payment_at: Optional[datetime] = None
    last_error: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class SetRecurringPaymentDto:
    subscription_id: int
    enabled: bool

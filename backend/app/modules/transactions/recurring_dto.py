from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.core.enums import PurchaseChannel
from app.modules.transactions.recurring_terms import RecurringTerms


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
    consent_id: Optional[int] = None
    first_failure_at: Optional[datetime] = None
    retry_count: int = 0
    cycle_expire_at: Optional[datetime] = None
    pending_since: Optional[datetime] = None
    upcoming_notified_for: Optional[datetime] = None
    next_attempt_at: Optional[datetime] = None
    leased_until: Optional[datetime] = None
    bank_retry_at: Optional[datetime] = None


class RecurringPaymentState(BaseModel):
    subscription_id: int
    terms: Optional[RecurringTerms] = None
    accepted_terms: Optional[RecurringTerms] = None
    enabled: bool
    available: bool
    customer_disabled: bool = False
    paused: bool = False
    retrying: bool = False
    payment_pending: bool = False
    next_retry_at: Optional[datetime] = None
    amount_limit: Optional[Decimal] = None
    currency: Optional[str] = None
    duration_days: Optional[int] = None
    next_payment_at: Optional[datetime] = None
    last_error: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class SetRecurringPaymentDto:
    subscription_id: int
    enabled: bool
    terms_id: Optional[str] = None
    channel: PurchaseChannel = PurchaseChannel.CABINET
    event_id: Optional[str] = None
    client_ip: Optional[str] = None

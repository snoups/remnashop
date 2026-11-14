from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel

from app.core.constants import DEFAULT_PAGE_SIZE
from app.modules.transactions.recurring_policy import RecurringState


@dataclass(frozen=True, kw_only=True)
class ListRecurringPaymentsDto:
    state: Optional[RecurringState] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


class RecurringPaymentAdminItem(BaseModel):
    subscription_id: int
    user_id: int
    user_name: Optional[str]
    plan_name: str
    enabled: bool
    customer_disabled: bool
    state: RecurringState
    last_error: Optional[str]
    next_attempt_at: Optional[datetime]
    submitted_at: Optional[datetime]
    pending_transaction_id: Optional[int]
    external_payment_id: Optional[str]
    can_check: bool
    can_close: bool
    can_retry: bool
    retry_count: int
    first_failure_at: Optional[datetime]
    amount_limit: Optional[Decimal]
    currency: Optional[str]
    expire_at: datetime


class RecurringPaymentAdminSummary(BaseModel):
    total: int
    enabled: int
    disabled: int
    pending: int
    retrying: int
    attention: int
    paid_renewals: int
    failed_renewals: int
    revenue: Decimal
    currency: str = "RUB"


class RecurringPaymentAdminPage(BaseModel):
    items: list[RecurringPaymentAdminItem]
    total: int
    page: int
    page_size: int
    summary: RecurringPaymentAdminSummary


RecurringAction = Literal["check", "close", "retry"]


@dataclass(frozen=True, kw_only=True)
class ManageRecurringPaymentDto:
    subscription_id: int
    action: RecurringAction
    expected_pending_transaction_id: Optional[int] = None
    client_ip: Optional[str] = None

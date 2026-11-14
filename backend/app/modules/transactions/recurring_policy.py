from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Callable, Final, Optional, Protocol, TypeVar

SAFE_REPOST_WINDOW: Final[timedelta] = timedelta(hours=23)
RETRY_OFFSETS_HOURS: Final[tuple[int, ...]] = (1, 3, 6, 12, 24, 36, 48, 72)
POLICY_RECHECK_DELAY: Final[timedelta] = timedelta(hours=1)


class RetryKind(StrEnum):
    NONE = "none"
    TECHNICAL = "technical"
    BANK = "bank"
    POLL = "poll"


@dataclass(frozen=True)
class ReasonPolicy:
    retry: RetryKind
    customer_notice: bool = True
    admin_notice: bool = True
    terminal: bool = False
    attention: bool = True
    block_enable: bool = True

    @property
    def allows_debit(self) -> bool:
        return self.retry in {RetryKind.TECHNICAL, RetryKind.BANK}


class RecurringReason(StrEnum):
    CUSTOMER_DISABLED = "customer_disabled"
    ADMIN_CLOSED = "admin_closed"
    BANK_DECLINED = "bank_declined"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    ISSUER_UNAVAILABLE = "issuer_unavailable"
    PAYMENT_METHOD_UNAVAILABLE = "payment_method_unavailable"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MERCHANT_UNAVAILABLE = "merchant_unavailable"
    PROVIDER_CONFIGURATION_ERROR = "provider_configuration_error"
    PROVIDER_REJECTED = "provider_rejected"
    PERMISSION_REVOKED = "permission_revoked"
    PAYMENT_METHOD_RESTRICTED = "payment_method_restricted"
    CARD_EXPIRED = "card_expired"
    FRAUD_SUSPECTED = "fraud_suspected"
    PRICE_CHANGED = "price_changed"
    SUBSCRIPTION_CHANGED = "subscription_changed"
    SHOP_CHANGED = "shop_changed"
    CONSENT_REQUIRED = "consent_required"
    PLAN_UNAVAILABLE = "plan_unavailable"
    CUSTOMER_EMAIL_REQUIRED = "customer_email_required"
    GATEWAY_DISABLED = "gateway_disabled"
    SUBSCRIPTION_UNAVAILABLE = "subscription_unavailable"
    PAYMENT_STATUS_UNKNOWN = "payment_status_unknown"
    PENDING_TIMEOUT = "pending_timeout"
    RETRIES_EXHAUSTED = "retries_exhausted"
    PAYMENT_METHOD_NOT_SAVED = "payment_method_not_saved"
    RENEWAL_WINDOW_EXPIRED = "renewal_window_expired"

    @property
    def policy(self) -> ReasonPolicy:
        return _REASON_POLICIES[self]


_BANK = ReasonPolicy(RetryKind.BANK, attention=False, block_enable=False)
_TECHNICAL = ReasonPolicy(RetryKind.TECHNICAL, customer_notice=False)
_TERMINAL = ReasonPolicy(RetryKind.NONE, terminal=True)
_REASON_POLICIES: Final[dict[RecurringReason, ReasonPolicy]] = {
    RecurringReason.CUSTOMER_DISABLED: ReasonPolicy(
        RetryKind.NONE,
        customer_notice=False,
        admin_notice=False,
        attention=False,
        block_enable=False,
    ),
    RecurringReason.ADMIN_CLOSED: ReasonPolicy(RetryKind.NONE, terminal=True, block_enable=False),
    RecurringReason.BANK_DECLINED: _BANK,
    RecurringReason.INSUFFICIENT_FUNDS: _BANK,
    RecurringReason.ISSUER_UNAVAILABLE: _BANK,
    RecurringReason.PAYMENT_METHOD_UNAVAILABLE: _BANK,
    RecurringReason.PROVIDER_REJECTED: _BANK,
    RecurringReason.PROVIDER_UNAVAILABLE: _TECHNICAL,
    RecurringReason.MERCHANT_UNAVAILABLE: _TECHNICAL,
    RecurringReason.PROVIDER_CONFIGURATION_ERROR: ReasonPolicy(
        RetryKind.NONE, customer_notice=False, terminal=True
    ),
    RecurringReason.PERMISSION_REVOKED: _TERMINAL,
    RecurringReason.PAYMENT_METHOD_RESTRICTED: _TERMINAL,
    RecurringReason.CARD_EXPIRED: _TERMINAL,
    RecurringReason.FRAUD_SUSPECTED: _TERMINAL,
    RecurringReason.PRICE_CHANGED: ReasonPolicy(RetryKind.TECHNICAL),
    RecurringReason.SUBSCRIPTION_CHANGED: _TERMINAL,
    RecurringReason.SHOP_CHANGED: _TECHNICAL,
    RecurringReason.CONSENT_REQUIRED: _TERMINAL,
    RecurringReason.PLAN_UNAVAILABLE: _TECHNICAL,
    RecurringReason.CUSTOMER_EMAIL_REQUIRED: _TECHNICAL,
    RecurringReason.GATEWAY_DISABLED: _TECHNICAL,
    RecurringReason.SUBSCRIPTION_UNAVAILABLE: ReasonPolicy(
        RetryKind.NONE, customer_notice=False, terminal=True
    ),
    RecurringReason.PAYMENT_STATUS_UNKNOWN: _TERMINAL,
    RecurringReason.PENDING_TIMEOUT: ReasonPolicy(RetryKind.POLL),
    RecurringReason.RETRIES_EXHAUSTED: _TERMINAL,
    RecurringReason.PAYMENT_METHOD_NOT_SAVED: _TERMINAL,
    RecurringReason.RENEWAL_WINDOW_EXPIRED: _TERMINAL,
}


def recurring_reason(value: Optional[str]) -> Optional[RecurringReason]:
    if value is None:
        return None
    try:
        return RecurringReason(value)
    except ValueError:
        return RecurringReason.BANK_DECLINED


class RecurringState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    PENDING = "pending"
    RETRYING = "retrying"
    ATTENTION = "attention"


_T = TypeVar("_T")


def classification_rules(
    *,
    enabled: _T,
    customer_disabled: _T,
    pending: _T,
    failed: _T,
    attention: _T,
    has_error: _T,
    combine: Callable[[_T, _T], _T],
) -> tuple[tuple[_T, RecurringState], ...]:
    # The same ordered rules drive SQL filters and the customer-facing state.
    return (
        (customer_disabled, RecurringState.DISABLED),
        (attention, RecurringState.ATTENTION),
        (pending, RecurringState.PENDING),
        (combine(enabled, failed), RecurringState.RETRYING),
        (has_error, RecurringState.ATTENTION),
        (enabled, RecurringState.ENABLED),
    )


class MandateState(Protocol):
    @property
    def enabled(self) -> bool: ...
    @property
    def customer_disabled(self) -> bool: ...
    @property
    def pending_transaction_id(self) -> Optional[int]: ...
    @property
    def first_failure_at(self) -> Optional[datetime]: ...
    @property
    def last_error(self) -> Optional[str]: ...
    @property
    def submitted_at(self) -> Optional[datetime]: ...


def classify(mandate: MandateState) -> RecurringState:
    reason = recurring_reason(mandate.last_error)
    for matches, state in classification_rules(
        enabled=mandate.enabled,
        customer_disabled=mandate.customer_disabled,
        pending=mandate.pending_transaction_id is not None,
        failed=mandate.first_failure_at is not None,
        attention=(reason is not None and reason.policy.attention)
        or (mandate.submitted_at is not None and mandate.pending_transaction_id is None),
        has_error=reason is not None,
        combine=lambda first, second: first and second,
    ):
        if matches:
            return state
    return RecurringState.DISABLED

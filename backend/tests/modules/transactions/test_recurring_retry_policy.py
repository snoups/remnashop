from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.utils.time import datetime_now
from app.modules.transactions.recurring_policy import (
    RETRY_OFFSETS_HOURS,
    RecurringReason,
    RecurringState,
    classify,
)


@pytest.mark.parametrize("reason", list(RecurringReason))
def test_every_reason_has_an_explicit_notification_policy_and_both_translations(reason):
    assets = Path(__file__).parents[3] / "assets" / "translations"
    for locale in ("ru", "en"):
        assert f"[{reason.value}]" in (assets / locale / "notifications.ftl").read_text()
    assert isinstance(reason.policy.customer_notice, bool)


@pytest.mark.parametrize(
    ("enabled", "customer_disabled", "pending", "failed", "reason", "expected"),
    [
        (True, False, None, None, None, RecurringState.ENABLED),
        (True, False, 1, None, None, RecurringState.PENDING),
        (True, False, None, datetime_now(), "insufficient_funds", RecurringState.RETRYING),
        (False, False, None, None, "payment_status_unknown", RecurringState.ATTENTION),
        (True, False, 1, None, "pending_timeout", RecurringState.ATTENTION),
        (False, True, 1, None, "customer_disabled", RecurringState.DISABLED),
    ],
)
def test_mandate_state_follows_one_ordered_policy(
    enabled, customer_disabled, pending, failed, reason, expected
):
    mandate = SimpleNamespace(
        enabled=enabled,
        customer_disabled=customer_disabled,
        pending_transaction_id=pending,
        first_failure_at=failed,
        last_error=reason,
        submitted_at=None,
    )
    assert classify(mandate) is expected


def test_bank_retry_schedule_has_the_agreed_absolute_offsets():
    assert RETRY_OFFSETS_HOURS == (1, 3, 6, 12, 24, 36, 48, 72)

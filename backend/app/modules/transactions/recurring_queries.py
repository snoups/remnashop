from datetime import datetime, timedelta
from typing import cast

from sqlalchemy import Integer, and_, case, or_
from sqlalchemy.sql.elements import ColumnElement

from app.core.db.models import RecurringConsent, RecurringPayment, Subscription
from app.modules.transactions.recurring_policy import (
    RecurringReason,
    RecurringState,
    classification_rules,
)


def recurring_state_expression() -> ColumnElement[str]:
    return case(
        *classification_rules(
            enabled=cast(ColumnElement[bool], RecurringPayment.enabled.is_(True)),
            customer_disabled=RecurringPayment.customer_disabled.is_(True),
            pending=RecurringPayment.pending_transaction_id.is_not(None),
            failed=RecurringPayment.first_failure_at.is_not(None),
            attention=or_(
                RecurringPayment.last_error.in_(
                    [reason.value for reason in RecurringReason if reason.policy.attention]
                ),
                and_(
                    RecurringPayment.submitted_at.is_not(None),
                    RecurringPayment.pending_transaction_id.is_(None),
                ),
            ),
            has_error=RecurringPayment.last_error.is_not(None),
            combine=lambda first, second: and_(first, second),
        ),
        else_=RecurringState.DISABLED.value,
    )


def renewal_window_expired(now: datetime) -> ColumnElement[bool]:
    raw_hours = RecurringConsent.terms["max_overdue_hours"].astext
    # A damaged authorization must not break the entire scheduler with a failed cast.
    hours = case((raw_hours.op("~")(r"^[0-9]{1,3}$"), raw_hours.cast(Integer)), else_=0)
    return Subscription.expire_at + hours * timedelta(hours=1) < now

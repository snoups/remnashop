from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from remnapy.enums import TrafficLimitStrategy

from app.core.constants import GB_TO_BYTES
from app.core.enums import Currency, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.utils.time import datetime_now
from app.modules.subscriptions.domain import (
    VALID_TRANSITIONS,
    SubscriptionState,
    assert_transition,
    calculate_proration_credit,
)
from app.modules.subscriptions.dto import PlanSnapshot


def _snapshot(**overrides: object) -> PlanSnapshot:
    defaults: dict[str, object] = {
        "plan_id": 1,
        "public_code": "basic",
        "name": "Basic",
        "price_paid": Decimal("300.00"),
        "currency": Currency.RUB,
        "duration_days": 30,
        "traffic_limit": 100,
        "device_limit": 3,
        "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET,
        "is_trial": False,
    }
    defaults.update(overrides)
    return PlanSnapshot(**defaults)  # type: ignore[arg-type]


def _state(**overrides: object) -> SubscriptionState:
    defaults: dict[str, object] = {
        "id": 1,
        "status": SubscriptionStatus.ACTIVE,
        "expire_at": datetime(2026, 9, 1),  # noqa: DTZ001
        "plan_snapshot": _snapshot(),
        "traffic_limit": 100,
        "device_limit": 3,
        "traffic_limit_strategy": None,
        "internal_squads": [],
        "external_squad": None,
        "is_trial": False,
    }
    defaults.update(overrides)
    return SubscriptionState(**defaults)  # type: ignore[arg-type]


def test_valid_transitions_is_total_over_every_status() -> None:
    for status in SubscriptionStatus:
        assert status in VALID_TRANSITIONS, f"{status} has no transition entry"


def test_deleted_is_terminal() -> None:
    assert VALID_TRANSITIONS[SubscriptionStatus.DELETED] == frozenset({SubscriptionStatus.DELETED})


@pytest.mark.parametrize(
    "current,target",
    [
        (SubscriptionStatus.ACTIVE, SubscriptionStatus.LIMITED),
        (SubscriptionStatus.LIMITED, SubscriptionStatus.ACTIVE),
        (SubscriptionStatus.ACTIVE, SubscriptionStatus.DELETED),
        (SubscriptionStatus.EXPIRED, SubscriptionStatus.ACTIVE),
    ],
)
def test_legal_transitions_do_not_raise(
    current: SubscriptionStatus, target: SubscriptionStatus
) -> None:
    assert_transition(current, target)  # must not raise


@pytest.mark.parametrize(
    "current,target",
    [
        (SubscriptionStatus.DELETED, SubscriptionStatus.ACTIVE),
        (SubscriptionStatus.DELETED, SubscriptionStatus.EXPIRED),
    ],
)
def test_illegal_transitions_raise(current: SubscriptionStatus, target: SubscriptionStatus) -> None:
    with pytest.raises(ValidationError):
        assert_transition(current, target)


def test_sync_status_is_a_noop_when_already_deleted() -> None:
    state = _state(status=SubscriptionStatus.DELETED)

    result = state.sync_status(SubscriptionStatus.ACTIVE)

    assert result.status is SubscriptionStatus.DELETED


def test_sync_status_is_a_noop_on_redelivery() -> None:
    state = _state(status=SubscriptionStatus.LIMITED)

    result = state.sync_status(SubscriptionStatus.LIMITED)

    assert result is state


def test_sync_status_applies_a_legal_transition() -> None:
    state = _state(status=SubscriptionStatus.ACTIVE)

    result = state.sync_status(SubscriptionStatus.LIMITED)

    assert result.status is SubscriptionStatus.LIMITED


def test_sync_status_accepts_any_panel_status_unconditionally() -> None:
    # The panel is authoritative. sync_status must accept any status update
    # from the panel, even if it would violate the general transition table.
    # E.g. a locally-EXPIRED subscription can receive LIMITED/DISABLED from
    # the panel (the user was already expired, but the panel wants to mark
    # them as limited for another reason). sync_status should not reject this.
    state = _state(status=SubscriptionStatus.EXPIRED)

    result = state.sync_status(SubscriptionStatus.LIMITED)

    assert result.status is SubscriptionStatus.LIMITED


def test_reactivate_on_renew_from_expired_goes_to_active() -> None:
    state = _state(status=SubscriptionStatus.EXPIRED, expire_at=datetime(2026, 1, 1))  # noqa: DTZ001
    new_expire_at = datetime(2026, 10, 1)  # noqa: DTZ001

    result = state.reactivate_on_renew(new_expire_at)

    assert result.status is SubscriptionStatus.ACTIVE
    assert result.expire_at == new_expire_at


def test_reactivate_on_renew_from_limited_stays_limited() -> None:
    state = _state(status=SubscriptionStatus.LIMITED)
    new_expire_at = datetime(2026, 10, 1)  # noqa: DTZ001

    result = state.reactivate_on_renew(new_expire_at)

    assert result.status is SubscriptionStatus.LIMITED
    assert result.expire_at == new_expire_at


def test_reactivate_on_renew_rejects_deleted() -> None:
    state = _state(status=SubscriptionStatus.DELETED)

    with pytest.raises(ValidationError):
        state.reactivate_on_renew(datetime(2026, 10, 1))  # noqa: DTZ001


def test_sync_expire_at_never_changes_status() -> None:
    state = _state(status=SubscriptionStatus.EXPIRED, expire_at=datetime(2026, 1, 1))  # noqa: DTZ001
    new_expire_at = datetime(2026, 2, 1)  # noqa: DTZ001

    result = state.sync_expire_at(new_expire_at)

    assert result.status is SubscriptionStatus.EXPIRED
    assert result.expire_at == new_expire_at


def test_sync_expire_at_is_a_noop_when_already_deleted() -> None:
    state = _state(status=SubscriptionStatus.DELETED, expire_at=datetime(2026, 1, 1))  # noqa: DTZ001

    assert state.sync_expire_at(datetime(2026, 2, 1)) is state  # noqa: DTZ001


def _credit(
    *,
    used_gb: int,
    traffic_limit: int = 100,
    strategy: TrafficLimitStrategy = TrafficLimitStrategy.NO_RESET,
) -> Decimal:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return calculate_proration_credit(
        credit_paid=Decimal("300"),
        credit_days=30,
        expire_at=now + timedelta(days=20),
        is_trial=False,
        now=now,
        traffic_limit=traffic_limit,
        traffic_limit_strategy=strategy,
        used_traffic_bytes=used_gb * GB_TO_BYTES,
    )


@pytest.mark.parametrize(
    ("used_gb", "expected"),
    [(10, Decimal("200")), (50, Decimal("150")), (95, Decimal("15")), (120, Decimal("0"))],
)
def test_proration_credit_takes_the_smaller_of_days_and_traffic_left(
    used_gb: int, expected: Decimal
) -> None:
    assert _credit(used_gb=used_gb) == expected


def test_proration_credit_ignores_traffic_on_an_unlimited_plan() -> None:
    assert _credit(used_gb=95, traffic_limit=0) == Decimal("200")


def test_proration_credit_ignores_a_counter_that_resets_every_period() -> None:
    assert _credit(used_gb=95, strategy=TrafficLimitStrategy.MONTH) == Decimal("200")


@pytest.mark.parametrize(
    ("credit_paid", "credit_days", "remaining", "expected"),
    [
        (Decimal("700"), 395, 395, Decimal("700")),
        (Decimal("100"), 30, 400, Decimal("100")),
        (Decimal("700"), 395, 100, Decimal("700") / 395 * 100),
    ],
)
def test_proration_credit_is_capped_at_what_was_paid(
    credit_paid: Decimal, credit_days: int, remaining: int, expected: Decimal
) -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    credit = calculate_proration_credit(
        credit_paid=credit_paid,
        credit_days=credit_days,
        expire_at=now + timedelta(days=remaining),
        is_trial=False,
        now=now,
        traffic_limit=0,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        used_traffic_bytes=0,
    )

    assert credit == expected


def test_renewal_credit_restarts_after_a_lapsed_term() -> None:
    state = _state(plan_snapshot=_snapshot(credit_paid=Decimal("500"), credit_days=60))

    restarted = state.add_renewal_credit(Decimal("100"), 30, restart=True)
    accumulated = state.add_renewal_credit(Decimal("100"), 30)

    assert restarted.plan_snapshot.credit_paid == Decimal("100")
    assert restarted.plan_snapshot.credit_days == 30
    assert accumulated.plan_snapshot.credit_paid == Decimal("600")
    assert accumulated.plan_snapshot.credit_days == 90


def test_shorten_after_refund_moves_expiry_back_and_drops_credit() -> None:
    now = datetime_now()
    state = _state(
        status=SubscriptionStatus.ACTIVE,
        expire_at=now + timedelta(days=40),
        plan_snapshot=_snapshot(credit_paid=Decimal("200"), credit_days=40),
    )
    shortened = state.shorten_after_refund(30, Decimal("150"), now)
    assert shortened.expire_at == now + timedelta(days=10)
    assert shortened.status is SubscriptionStatus.ACTIVE
    assert shortened.plan_snapshot.credit_paid == Decimal("50")
    assert shortened.plan_snapshot.credit_days == 10


def test_shorten_after_refund_into_the_past_expires() -> None:
    now = datetime_now()
    state = _state(status=SubscriptionStatus.ACTIVE, expire_at=now + timedelta(days=5))
    shortened = state.shorten_after_refund(30, Decimal("0"), now)
    assert shortened.status is SubscriptionStatus.EXPIRED
    # credit never goes negative
    assert shortened.plan_snapshot.credit_days == 0


def test_shorten_after_refund_expires_a_limited_subscription() -> None:
    now = datetime_now()
    state = _state(status=SubscriptionStatus.LIMITED, expire_at=now + timedelta(days=5))
    shortened = state.shorten_after_refund(30, Decimal("0"), now)
    assert shortened.status is SubscriptionStatus.EXPIRED


def test_shorten_after_refund_refuses_a_deleted_subscription() -> None:
    now = datetime_now()
    state = _state(status=SubscriptionStatus.DELETED, expire_at=now + timedelta(days=40))
    with pytest.raises(ValidationError):
        state.shorten_after_refund(30, Decimal("0"), now)


def test_restore_after_refund_reactivates_a_deleted_row() -> None:
    now = datetime_now()
    state = _state(status=SubscriptionStatus.DELETED, expire_at=now + timedelta(days=3))
    assert state.restore_after_refund(now).status is SubscriptionStatus.ACTIVE


def test_restore_after_refund_with_a_lapsed_term_is_expired() -> None:
    now = datetime_now()
    state = _state(status=SubscriptionStatus.DELETED, expire_at=now - timedelta(days=1))
    assert state.restore_after_refund(now).status is SubscriptionStatus.EXPIRED


def test_restore_after_refund_refuses_a_live_row() -> None:
    now = datetime_now()
    state = _state(status=SubscriptionStatus.ACTIVE, expire_at=now + timedelta(days=3))
    with pytest.raises(ValidationError) as exc:
        state.restore_after_refund(now)
    assert exc.value.code is ErrorCode.SUBSCRIPTION_STATUS_TRANSITION_INVALID

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from remnapy.enums import TrafficLimitStrategy

from app.core.enums import Currency, SubscriptionStatus
from app.core.exceptions import ValidationError
from app.modules.subscriptions.domain import VALID_TRANSITIONS, SubscriptionState, assert_transition
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


def test_change_plan_in_place_applies_new_plan_on_the_same_state() -> None:
    new_squad = uuid4()
    state = _state(
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime(2026, 1, 31),  # noqa: DTZ001
        plan_snapshot=_snapshot(plan_id=1, price_paid=Decimal("300.00")),
    )
    new_snapshot = _snapshot(
        plan_id=2,
        price_paid=Decimal("500.00"),
        traffic_limit=200,
        device_limit=5,
        internal_squads=[new_squad],
    )
    new_expire_at = datetime(2026, 3, 1)  # noqa: DTZ001

    new_state = state.change_plan_in_place(
        new_plan_snapshot=new_snapshot, new_expire_at=new_expire_at
    )

    assert new_state.id == state.id
    assert new_state.status is SubscriptionStatus.ACTIVE
    assert new_state.plan_snapshot == new_snapshot
    assert new_state.traffic_limit == 200
    assert new_state.device_limit == 5
    assert new_state.internal_squads == [new_squad]
    assert new_state.expire_at == new_expire_at


def test_change_plan_in_place_reactivates_a_limited_subscription() -> None:
    state = _state(status=SubscriptionStatus.LIMITED)

    new_state = state.change_plan_in_place(
        new_plan_snapshot=_snapshot(),
        new_expire_at=datetime(2026, 3, 1),  # noqa: DTZ001
    )

    assert new_state.status is SubscriptionStatus.ACTIVE


def test_change_plan_in_place_rejects_a_deleted_subscription() -> None:
    state = _state(status=SubscriptionStatus.DELETED)

    with pytest.raises(ValidationError):
        state.change_plan_in_place(
            new_plan_snapshot=_snapshot(),
            new_expire_at=datetime(2026, 3, 1),  # noqa: DTZ001
        )

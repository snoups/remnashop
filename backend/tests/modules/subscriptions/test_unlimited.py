from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.enums import PlanType
from app.modules.plans.dto import PlanDto, PlanDurationDto
from app.modules.subscriptions.dto import PlanSnapshot
from app.modules.subscriptions.unlimited import expiry_after, is_unlimited_expiry
from tests.modules.subscriptions.factories import make_plan_snapshot, make_subscription_dto


def test_expiry_after_zero_is_year_2099_same_day() -> None:
    start = datetime(2026, 11, 14, 10, 30, tzinfo=timezone.utc)

    assert expiry_after(start, 0) == datetime(2099, 11, 14, 10, 30, tzinfo=timezone.utc)


def test_expiry_after_feb_29_clamps() -> None:
    start = datetime(2028, 2, 29, tzinfo=timezone.utc)

    assert expiry_after(start, 0) == datetime(2099, 2, 28, tzinfo=timezone.utc)


def test_expiry_after_days_adds() -> None:
    start = datetime(2026, 11, 14, tzinfo=timezone.utc)

    assert expiry_after(start, 30) == start + timedelta(days=30)


def test_expiry_after_negative_raises() -> None:
    with pytest.raises(ValueError):
        expiry_after(datetime(2026, 1, 1, tzinfo=timezone.utc), -1)


def test_is_unlimited_expiry_threshold() -> None:
    assert not is_unlimited_expiry(datetime(2098, 12, 31, 23, 59, tzinfo=timezone.utc))
    assert is_unlimited_expiry(datetime(2099, 1, 1, tzinfo=timezone.utc))
    assert is_unlimited_expiry(datetime(2105, 6, 1, tzinfo=timezone.utc))


def test_plan_snapshot_unlimited_from_round_trips() -> None:
    before = datetime(2026, 12, 1, tzinfo=timezone.utc)
    snapshot = make_plan_snapshot(
        unlimited_from=before,
        unlimited_from_credit_paid=Decimal("300"),
        unlimited_from_credit_days=30,
    )

    restored = PlanSnapshot.from_json(snapshot.to_json())

    assert restored.unlimited_from == before
    assert restored.unlimited_from_credit_paid == Decimal("300")
    assert restored.unlimited_from_credit_days == 30


def test_plan_snapshot_without_unlimited_keys_reads_none() -> None:
    data = make_plan_snapshot().to_json()
    for key in ("unlimited_from", "unlimited_from_credit_paid", "unlimited_from_credit_days"):
        data.pop(key, None)

    restored = PlanSnapshot.from_json(data)

    assert restored.unlimited_from is None
    assert restored.unlimited_from_credit_paid is None
    assert restored.unlimited_from_credit_days is None


def test_subscription_dto_is_unlimited() -> None:
    assert make_subscription_dto(expire_at=datetime(2099, 3, 1, tzinfo=timezone.utc)).is_unlimited
    assert not make_subscription_dto(
        expire_at=datetime(2027, 3, 1, tzinfo=timezone.utc)
    ).is_unlimited


def test_a_trial_never_offers_an_unlimited_duration() -> None:
    trial = PlanDto(
        public_code="trial",
        name="Trial",
        type=PlanType.BOTH,
        traffic_limit=1,
        device_limit=1,
        is_trial=True,
        durations=[PlanDurationDto(id=1, days=0, base_price=Decimal("0"))],
    )

    assert trial.sellable_durations() == []
    assert trial.free_trial_duration() is None

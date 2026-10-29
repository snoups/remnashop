from decimal import Decimal
from uuid import uuid4

import pytest
from remnapy.enums import TrafficLimitStrategy

from app.core.enums import Currency
from app.modules.subscriptions.dto import PlanSnapshot
from tests.modules.subscriptions.factories import make_plan_snapshot


def test_round_trips_through_json() -> None:
    squad = uuid4()
    snapshot = PlanSnapshot(
        plan_id=7,
        public_code="basic",
        name="Basic",
        price_paid=Decimal("299.50"),
        currency=Currency.RUB,
        duration_days=30,
        traffic_limit=100,
        device_limit=3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        is_trial=False,
        internal_squads=[squad],
        external_squad=uuid4(),
        tag="VIP",
    )

    restored = PlanSnapshot.from_json(snapshot.to_json())

    assert restored == snapshot


def test_round_trips_with_no_squads() -> None:
    snapshot = PlanSnapshot(
        plan_id=7,
        public_code="basic",
        name="Basic",
        price_paid=Decimal("299.50"),
        currency=Currency.RUB,
        duration_days=30,
        traffic_limit=100,
        device_limit=3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        is_trial=False,
    )

    restored = PlanSnapshot.from_json(snapshot.to_json())

    assert restored == snapshot


def test_reads_a_snapshot_written_before_the_tag_as_untagged() -> None:
    data = make_plan_snapshot().to_json()
    del data["tag"]

    assert PlanSnapshot.from_json(data).tag is None


def test_from_json_raises_on_missing_key() -> None:
    with pytest.raises(KeyError):
        PlanSnapshot.from_json({"plan_id": 1, "public_code": "basic"})


def test_to_json_serializes_price_and_currency_as_strings() -> None:
    snapshot = PlanSnapshot(
        plan_id=1,
        public_code="basic",
        name="Basic",
        price_paid=Decimal("10.00"),
        currency=Currency.USD,
        duration_days=7,
        traffic_limit=100,
        device_limit=3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        is_trial=False,
    )

    data = snapshot.to_json()

    assert data["price_paid"] == "10.00"
    assert data["currency"] == "USD"


def test_credit_fields_round_trip_and_old_json_reads_as_none() -> None:
    snapshot = make_plan_snapshot(credit_paid=Decimal("700"), credit_days=395)
    data = snapshot.to_json()

    assert PlanSnapshot.from_json(data) == snapshot

    del data["credit_paid"], data["credit_days"]
    old = PlanSnapshot.from_json(data)
    assert old.credit_paid is None
    assert old.credit_days is None

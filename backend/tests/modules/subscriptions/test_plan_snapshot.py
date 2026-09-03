from decimal import Decimal
from uuid import uuid4

import pytest
from remnapy.enums import TrafficLimitStrategy

from app.core.enums import Currency
from app.modules.subscriptions.dto import PlanSnapshot


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

from decimal import Decimal

import pytest

from app.core.enums import Currency
from app.modules.subscriptions.dto import PlanSnapshot


def test_round_trips_through_json() -> None:
    snapshot = PlanSnapshot(
        plan_id=7,
        public_code="basic",
        name="Basic",
        price_paid=Decimal("299.50"),
        currency=Currency.RUB,
        duration_days=30,
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
    )

    data = snapshot.to_json()

    assert data["price_paid"] == "10.00"
    assert data["currency"] == "USD"

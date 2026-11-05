from decimal import Decimal
from typing import Any

from app.cli.legacy.plans import transform_plans
from app.cli.legacy.report import MigrationReport
from app.core.enums import Currency

PLAN: dict[str, Any] = {
    "id": 3,
    "public_code": "pro",
    "name": "Pro",
    "description": None,
    "tag": None,
    "type": "BOTH",
    "availability": "ALL",
    "traffic_limit_strategy": "MONTH",
    "traffic_limit": 100,
    "device_limit": 3,
    "allowed_telegram_ids": [],
    "allowed_emails": [],
    "internal_squads": [],
    "external_squad": None,
    "order_index": 1,
    "is_active": True,
    "is_trial": False,
}
DURATIONS = [{"id": 10, "plan_id": 3, "days": 30, "order_index": 1}]


def _price(price_id: int, currency: str, price: str, duration: int = 10) -> dict[str, Any]:
    return {
        "id": price_id,
        "plan_duration_id": duration,
        "currency": currency,
        "price": Decimal(price),
    }


def test_anchor_price_becomes_base_price() -> None:
    prices = [_price(1, "RUB", "900"), _price(2, "USD", "100"), _price(3, "XTR", "100")]
    rows = transform_plans(
        [PLAN], DURATIONS, prices, anchor_currency=Currency.RUB, report=MigrationReport()
    )
    assert rows.durations[0]["base_price"] == Decimal("900")
    assert {(o["currency"], o["price"]) for o in rows.overrides} == {
        (Currency.USD, Decimal("100")),
        (Currency.XTR, Decimal("100")),
    }
    assert all(o["plan_duration_id"] == 10 for o in rows.overrides)


def test_ids_preserved() -> None:
    rows = transform_plans(
        [PLAN],
        DURATIONS,
        [_price(1, "RUB", "900")],
        anchor_currency=Currency.RUB,
        report=MigrationReport(),
    )
    assert rows.plans[0]["id"] == 3
    assert rows.plans[0]["public_code"] == "pro"
    assert (rows.durations[0]["id"], rows.durations[0]["plan_id"]) == (10, 3)


def test_zero_trial_price_kept() -> None:
    rows = transform_plans(
        [PLAN],
        DURATIONS,
        [_price(1, "RUB", "0"), _price(2, "USD", "0")],
        anchor_currency=Currency.RUB,
        report=MigrationReport(),
    )
    assert rows.durations[0]["base_price"] == Decimal("0")
    assert rows.overrides[0]["price"] == Decimal("0")


def test_missing_anchor_price_becomes_overrides() -> None:
    report = MigrationReport()
    rows = transform_plans(
        [PLAN],
        DURATIONS,
        [_price(2, "USD", "5"), _price(3, "XTR", "100")],
        anchor_currency=Currency.RUB,
        report=report,
    )
    assert rows.durations[0]["base_price"] == Decimal("0")
    assert len(rows.overrides) == 2
    assert any("anchor" in note for note in report.notes)


def test_counts_reported() -> None:
    report = MigrationReport()
    transform_plans([PLAN], DURATIONS, [], anchor_currency=Currency.RUB, report=report)
    assert report.counts["plans"].migrated == 1

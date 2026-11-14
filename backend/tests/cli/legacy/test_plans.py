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
ALL: frozenset[Currency] = frozenset(Currency)


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
        [PLAN],
        DURATIONS,
        prices,
        anchor_currency=Currency.RUB,
        used_currencies=ALL,
        report=MigrationReport(),
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
        used_currencies=ALL,
        report=MigrationReport(),
    )
    assert rows.plans[0]["id"] == 3
    assert rows.plans[0]["public_code"] == "pro"
    assert (rows.durations[0]["id"], rows.durations[0]["plan_id"]) == (10, 3)


def test_free_trial_keeps_no_currency_pins() -> None:
    rows = transform_plans(
        [PLAN],
        DURATIONS,
        [_price(1, "RUB", "0"), _price(2, "USD", "0")],
        anchor_currency=Currency.RUB,
        used_currencies=ALL,
        report=MigrationReport(),
    )
    assert rows.durations[0]["base_price"] == Decimal("0")
    assert rows.overrides == []


def test_prices_in_currencies_the_shop_never_sold_in_are_dropped() -> None:
    report = MigrationReport()
    prices = [_price(1, "RUB", "900"), _price(2, "USD", "100"), _price(3, "XTR", "60")]

    rows = transform_plans(
        [PLAN],
        DURATIONS,
        prices,
        anchor_currency=Currency.RUB,
        used_currencies=frozenset({Currency.RUB, Currency.XTR}),
        report=report,
    )

    assert {(o["currency"], o["price"]) for o in rows.overrides} == {(Currency.XTR, Decimal("60"))}
    assert (report.counts["plan_prices"].source, report.counts["plan_prices"].migrated) == (3, 2)
    assert any("USD 1" in note and "default rate" in note for note in report.notes)


def test_missing_anchor_price_becomes_overrides() -> None:
    report = MigrationReport()
    rows = transform_plans(
        [PLAN],
        DURATIONS,
        [_price(2, "USD", "5"), _price(3, "XTR", "100")],
        anchor_currency=Currency.RUB,
        used_currencies=ALL,
        report=report,
    )
    assert rows.durations[0]["base_price"] == Decimal("0")
    assert len(rows.overrides) == 2
    assert any("anchor" in note for note in report.notes)


def test_counts_reported() -> None:
    report = MigrationReport()
    transform_plans(
        [PLAN], DURATIONS, [], anchor_currency=Currency.RUB, used_currencies=ALL, report=report
    )
    assert report.counts["plans"].migrated == 1


def test_leading_emoji_stripped_and_default_icon_set() -> None:
    names = {
        1: "🚀 Premium",
        2: "🇷🇺Россия 🔥",
        3: "👨‍👩‍👧  Семья",
        4: "👍🏽 Ок",
        5: "Basic",
        6: "🔥",
    }
    report = MigrationReport()
    rows = transform_plans(
        [{**PLAN, "id": i, "name": n} for i, n in names.items()],
        [],
        [],
        anchor_currency=Currency.RUB,
        used_currencies=ALL,
        report=report,
    )
    assert [p["name"] for p in rows.plans] == [
        "Premium",
        "Россия 🔥",
        "Семья",
        "Ок",
        "Basic",
        "🔥",
    ]
    assert {(p["icon_emoji_id"], p["icon_emoji_fallback"]) for p in rows.plans} == {
        ("5429613693287578957", "📦")
    }
    assert "plans: leading emoji removed from 4 plan names" in report.notes


def test_trial_with_unlimited_duration_is_reported() -> None:
    report = MigrationReport()
    trial = PLAN | {"id": 4, "name": "Trial", "is_trial": True}
    rows = transform_plans(
        [PLAN, trial],
        [*DURATIONS, {"id": 11, "plan_id": 4, "days": 0, "order_index": 1}],
        [_price(1, "RUB", "0", duration=11)],
        anchor_currency=Currency.RUB,
        used_currencies=ALL,
        report=report,
    )

    assert [row["days"] for row in rows.durations if row["plan_id"] == 4] == [0]
    assert any("Trial" in note and "unlimited" in note for note in report.notes)

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from app.cli.legacy.report import MigrationReport
from app.cli.legacy.transactions import transform_transactions
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseChannel,
    TransactionStatus,
)

CREATED = datetime(2026, 1, 1, tzinfo=timezone.utc)
UPDATED = datetime(2026, 1, 2, tzinfo=timezone.utc)
PAYMENT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SNAPSHOT: dict[str, Any] = {
    "id": 3,
    "tag": None,
    "name": "Pro",
    "type": "BOTH",
    "duration": 30,
    "is_trial": False,
    "device_limit": 3,
    "traffic_limit": 100,
    "external_squad": None,
    "internal_squads": [],
    "traffic_limit_strategy": "MONTH",
}
PRICING = {"original_amount": "2200.00", "final_amount": "1100", "discount_percent": 50}


def _row(**extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 7,
        "payment_id": PAYMENT_ID,
        "user_id": 1,
        "status": "COMPLETED",
        "is_test": False,
        "purchase_type": "NEW",
        "gateway_type": "YOOKASSA",
        "payment_method": "SBP",
        "pricing": PRICING,
        "currency": "RUB",
        "plan_snapshot": SNAPSHOT,
        "created_at": CREATED,
        "updated_at": UPDATED,
    }
    row.update(extra)
    return row


def _run(
    rows: list[dict[str, Any]],
    *,
    report: MigrationReport,
    plan_ids: Optional[set[int]] = None,
    subscription_ids: Optional[set[int]] = None,
    rates: Optional[dict[Currency, Decimal]] = None,
) -> list[dict[str, Any]]:
    return transform_transactions(
        rows,
        plan_ids={3} if plan_ids is None else plan_ids,
        subscription_ids=set() if subscription_ids is None else subscription_ids,
        anchor_currency=Currency.RUB,
        rates=rates or {},
        report=report,
    )


def _one(**extra: Any) -> dict[str, Any]:
    return _run([_row(**extra)], report=MigrationReport())[0]


def test_completed_becomes_paid() -> None:
    assert _one()["status"] is TransactionStatus.PAID
    assert _one(status="FAILED")["status"] is TransactionStatus.FAILED


def test_pricing_parsed() -> None:
    item = _one()
    assert item["base_price"] == Decimal("2200.00")
    assert item["final_price"] == Decimal("1100")
    assert item["discount_percent"] == 50
    assert item["discount_source"] is DiscountSource.PERSONAL
    assert item["discount_from_promocode"] is False


def test_no_discount_has_no_source() -> None:
    item = _one(pricing={"original_amount": "100", "final_amount": "100", "discount_percent": 0})
    assert item["discount_source"] is DiscountSource.NONE


def test_anchor_same_currency() -> None:
    item = _one()
    assert item["anchor_base_price"] == Decimal("2200.00")
    assert item["anchor_final_price"] == Decimal("1100")


def test_anchor_other_currency_uses_rate() -> None:
    rates = {Currency.RUB: Decimal("1"), Currency.USD: Decimal("0.01")}
    item = _run(
        [_row(currency="USD", pricing={"original_amount": "10", "final_amount": "5"})],
        rates=rates,
        report=MigrationReport(),
    )[0]
    assert item["anchor_base_price"] == Decimal("1000.00")
    assert item["anchor_final_price"] == Decimal("500.00")


def test_anchor_without_rate_noted() -> None:
    report = MigrationReport()
    item = _run(
        [_row(currency="USD", pricing={"original_amount": "10", "final_amount": "5"})],
        report=report,
    )[0]
    assert item["anchor_final_price"] == Decimal("5")
    assert any("rate" in note for note in report.notes)


def test_payment_id_becomes_idempotency_key() -> None:
    item = _one()
    assert item["idempotency_key"] == str(PAYMENT_ID)
    assert item["external_payment_id"] is None


def test_plan_id_from_snapshot() -> None:
    assert _one()["plan_id"] == 3
    assert _run([_row()], plan_ids=set(), report=MigrationReport())[0]["plan_id"] is None
    test_row = _row(plan_snapshot={**SNAPSHOT, "id": -1}, is_test=True)
    assert _run([test_row], plan_ids={3}, report=MigrationReport())[0]["plan_id"] is None


def test_snapshot_converted() -> None:
    snapshot = _one()["plan_snapshot"]
    assert snapshot["plan_id"] == 3
    assert snapshot["price_paid"] == "1100"
    assert snapshot["currency"] == "RUB"
    assert _one()["duration_days"] == 30


def test_missing_subscription_links_nulled() -> None:
    row = _row(target_subscription_id=5, fulfilled_subscription_id=6)
    kept = _run([row], subscription_ids={5}, report=MigrationReport())[0]
    assert kept["target_subscription_id"] == 5
    assert kept["fulfilled_subscription_id"] is None


def test_paid_sets_fulfilled_at() -> None:
    assert _one()["fulfilled_at"] == UPDATED
    assert _one(status="FAILED")["fulfilled_at"] is None


def test_channel_is_bot() -> None:
    item = _one()
    assert item["channel"] is PurchaseChannel.BOT
    assert item["expires_at"] == CREATED
    assert item["gateway_type"] is PaymentGatewayType.YOOKASSA

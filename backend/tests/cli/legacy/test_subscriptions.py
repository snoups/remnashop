from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.cli.legacy.panel import PanelIndex
from app.cli.legacy.report import MigrationReport
from app.cli.legacy.subscriptions import (
    convert_plan_snapshot,
    migrated_subscription_ids,
    transform_subscriptions,
)
from app.core.enums import Currency, SubscriptionStatus
from app.modules.subscriptions.dto import PlanSnapshot

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
SNAPSHOT: dict[str, Any] = {
    "id": 3,
    "tag": "PRO",
    "name": "Pro",
    "type": "BOTH",
    "duration": 30,
    "is_trial": False,
    "device_limit": 3,
    "traffic_limit": 100,
    "external_squad": None,
    "internal_squads": ["11111111-1111-1111-1111-111111111111"],
    "traffic_limit_strategy": "MONTH",
}
CONNECTED = datetime(2025, 12, 1, tzinfo=timezone.utc)
INDEX = PanelIndex(
    by_username={"rs_1001": 55}, by_telegram_id={}, first_connected_at={55: CONNECTED}
)
USERS = {1: {"telegram_id": 1001}, 2: {"telegram_id": 1002}}


def _row(sub_id: int, status: str = "ACTIVE", user_id: int = 1, **extra: Any) -> dict[str, Any]:
    return {
        "id": sub_id,
        "user_id": user_id,
        "status": status,
        "is_trial": False,
        "disabled_by_channel_leave": False,
        "traffic_limit": 100,
        "device_limit": 3,
        "traffic_limit_strategy": "MONTH",
        "tag": None,
        "internal_squads": [],
        "external_squad": None,
        "expire_at": NOW,
        "url": "https://sub.example.com/zzz",
        "plan_snapshot": SNAPSHOT,
        "device_single_reset_at": None,
        "device_all_reset_at": None,
        "link_reset_at": None,
        "created_at": NOW,
        "updated_at": NOW,
        **extra,
    }


def _run(
    rows: list[dict[str, Any]], current: set[int], report: MigrationReport
) -> list[dict[str, Any]]:
    return transform_subscriptions(
        rows,
        users=USERS,
        current_subscription_ids=current,
        index=INDEX,
        plan_codes={3: "pro"},
        last_payments={(1, 3): (Decimal("199"), Currency.RUB)},
        anchor_currency=Currency.USD,
        report=report,
    )


def test_only_current_subscription_stays_live() -> None:
    report = MigrationReport()
    result = _run([_row(73, "DISABLED"), _row(95, "DELETED"), _row(350)], {350}, report)
    status = {item["id"]: item["status"] for item in result}
    assert status == {
        73: SubscriptionStatus.DELETED,
        95: SubscriptionStatus.DELETED,
        350: SubscriptionStatus.ACTIVE,
    }


def test_user_without_current_subscription() -> None:
    result = _run([_row(1), _row(2)], set(), MigrationReport())
    assert {item["status"] for item in result} == {SubscriptionStatus.DELETED}


def test_missing_panel_user_not_migrated() -> None:
    report = MigrationReport()
    result = _run([_row(5, user_id=2)], {5}, report)
    assert result == []
    assert report.skips and "panel user" in report.skips[0].reason
    assert migrated_subscription_ids(result) == set()


def test_remnawave_user_id_from_panel_and_flag_renamed() -> None:
    result = _run([_row(1, disabled_by_channel_leave=True)], {1}, MigrationReport())
    assert result[0]["remnawave_user_id"] == 55
    assert result[0]["paused_by_channel_leave"] is True
    assert "disabled_by_channel_leave" not in result[0]


def test_first_connection_from_panel_on_every_subscription() -> None:
    result = _run([_row(1), _row(2, "EXPIRED")], {1}, MigrationReport())
    assert [item["first_connected_at"] for item in result] == [CONNECTED, CONNECTED]


def test_plan_snapshot_converted() -> None:
    result = _run([_row(1)], {1}, MigrationReport())
    snapshot = PlanSnapshot.from_json(result[0]["plan_snapshot"])
    assert snapshot.plan_id == 3
    assert snapshot.public_code == "pro"
    assert snapshot.duration_days == 30
    assert snapshot.price_paid == Decimal("199")
    assert snapshot.currency is Currency.RUB
    assert snapshot.device_limit == 3


def test_missing_plan_and_payment_fall_back_and_are_reported() -> None:
    report = MigrationReport()
    row = _row(1, plan_snapshot={**SNAPSHOT, "id": -1})
    result = _run([row], {1}, report)
    snapshot = PlanSnapshot.from_json(result[0]["plan_snapshot"])
    assert snapshot.public_code == ""
    assert (snapshot.price_paid, snapshot.currency) == (Decimal("0"), Currency.USD)
    assert any("priced at 0" in note for note in report.notes)
    assert any("empty public code" in note for note in report.notes)


def test_live_unique_per_panel_user() -> None:
    users = {1: {"telegram_id": 1001}, 3: {"telegram_id": 1001}}
    result = transform_subscriptions(
        [_row(1), _row(2, user_id=3)],
        users=users,
        current_subscription_ids={1, 2},
        index=INDEX,
        plan_codes={3: "pro"},
        last_payments={},
        anchor_currency=Currency.USD,
        report=MigrationReport(),
    )
    live = [i["remnawave_user_id"] for i in result if i["status"] is not SubscriptionStatus.DELETED]
    assert len(live) == len(set(live)) == 1


def test_convert_plan_snapshot_shape() -> None:
    out = convert_plan_snapshot(
        SNAPSHOT, public_code="pro", price_paid=Decimal("1"), currency=Currency.USD
    )
    assert out["credit_paid"] is None and out["credit_days"] is None

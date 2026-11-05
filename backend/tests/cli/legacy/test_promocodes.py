from datetime import datetime, timezone
from typing import Any

from app.cli.legacy.promocodes import transform_promocodes
from app.cli.legacy.report import MigrationReport
from app.core.enums import PromocodeAvailability, PromocodeRewardType

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _promo(**extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 1,
        "code": "GIFT",
        "is_active": True,
        "reward_type": "SUBSCRIPTION",
        "reward": None,
        "plan_snapshot": {"id": 4, "duration": 180},
        "availability": "ALL",
        "expires_at": None,
        "max_activations": 5,
        "is_reusable": False,
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.update(extra)
    return row


def test_subscription_promocode_reward_plan() -> None:
    promos, _ = transform_promocodes(
        [_promo()], [], plan_ids={4}, user_ids={1}, report=MigrationReport()
    )
    assert promos[0]["reward_plan_id"] == 4
    assert promos[0]["reward_duration_days"] == 180
    assert promos[0]["reward_type"] is PromocodeRewardType.SUBSCRIPTION
    assert promos[0]["availability"] is PromocodeAvailability.ALL
    assert promos[0]["is_active"] is True
    assert "plan_snapshot" not in promos[0]


def test_promocode_plan_missing_deactivated() -> None:
    report = MigrationReport()
    promos, _ = transform_promocodes([_promo()], [], plan_ids={9}, user_ids={1}, report=report)
    assert promos[0]["is_active"] is False
    assert "reward_plan_id" not in promos[0]
    assert any("plan" in note for note in report.notes)


def test_non_subscription_promocode_keeps_reward() -> None:
    promos, _ = transform_promocodes(
        [_promo(reward_type="DURATION", reward=7, plan_snapshot=None)],
        [],
        plan_ids=set(),
        user_ids=set(),
        report=MigrationReport(),
    )
    assert promos[0]["reward"] == 7
    assert promos[0]["is_active"] is True


def test_activation_subscription_null() -> None:
    report = MigrationReport()
    activation = {"id": 2, "promocode_id": 1, "user_id": 1, "activated_at": NOW}
    ghost = {"id": 3, "promocode_id": 1, "user_id": 99, "activated_at": NOW}
    _, activations = transform_promocodes(
        [_promo()], [activation, ghost], plan_ids={4}, user_ids={1}, report=report
    )
    assert activations == [
        {"id": 2, "promocode_id": 1, "user_id": 1, "subscription_id": None, "activated_at": NOW}
    ]
    assert report.skips[0].source_id == "3"

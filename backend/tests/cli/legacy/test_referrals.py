from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.cli.legacy.referrals import transform_referrals
from app.cli.legacy.report import MigrationReport
from app.core.enums import ReferralRewardType

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
REFERRAL = {
    "id": 1,
    "referrer_id": 10,
    "referred_id": 11,
    "level": 1,
    "created_at": NOW,
    "updated_at": NOW,
}


def _reward(**extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 5,
        "referral_id": 1,
        "user_id": 10,
        "type": "EXTRA_DAYS",
        "amount": 30,
        "is_issued": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.update(extra)
    return row


def _run(rewards: list[dict[str, Any]], report: MigrationReport) -> list[dict[str, Any]]:
    return transform_referrals(
        [REFERRAL], rewards, user_ids={10, 11}, subscription_ids=set(), report=report
    )[1]


def test_referral_copied() -> None:
    referrals, _ = transform_referrals(
        [REFERRAL], [], user_ids={10, 11}, subscription_ids=set(), report=MigrationReport()
    )
    assert referrals == [REFERRAL]


def test_rewards_issued_only() -> None:
    report = MigrationReport()
    rows = _run([_reward(), _reward(id=6, is_issued=False)], report)
    assert [r["id"] for r in rows] == [5]
    assert [s.source_id for s in report.skips] == ["6"]


def test_reward_amount_decimal() -> None:
    row = _run([_reward()], MigrationReport())[0]
    assert row["amount"] == Decimal(30)
    assert isinstance(row["amount"], Decimal)
    assert row["type"] is ReferralRewardType.EXTRA_DAYS


def test_reward_payment_key_legacy() -> None:
    assert _run([_reward()], MigrationReport())[0]["payment_key"] == "legacy:5"


def test_referrer_from_user_id() -> None:
    row = _run([_reward()], MigrationReport())[0]
    assert row["referrer_id"] == 10
    assert "user_id" not in row
    assert row["referral_id"] == 1

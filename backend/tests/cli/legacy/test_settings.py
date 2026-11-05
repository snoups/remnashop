from datetime import datetime, timezone
from typing import Any

from app.cli.legacy.report import MigrationReport
from app.cli.legacy.settings import transform_settings
from app.core.db.singleton import SINGLETON_ID
from app.core.enums import AccessMode, Currency, ReferralAccrualStrategy, ReferralRewardStrategy

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
REQUIREMENTS = {
    "channel_id": 0,
    "rules_link": "https://telegram.org/tos/",
    "channel_link": "@remna_shop",
    "rules_required": False,
    "channel_required": False,
}


def _row(**extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "default_currency": "RUB",
        "access": {"mode": "INVITED", "purchases_allowed": True, "registration_allowed": False},
        "requirements": REQUIREMENTS,
        "referral": {
            "level": 1,
            "enable": True,
            "reward": {"type": "EXTRA_DAYS", "config": {"1": 30}, "strategy": "AMOUNT"},
            "accrual_strategy": "ON_FIRST_PAYMENT",
        },
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.update(extra)
    return row


def test_access_settings() -> None:
    access = transform_settings(_row(), MigrationReport()).access
    assert access["id"] == SINGLETON_ID
    assert access["mode"] is AccessMode.INVITED
    assert access["payments_enabled"] is True
    assert access["registration_enabled"] is False


def test_requirements_to_bot_requirements() -> None:
    report = MigrationReport()
    req = transform_settings(_row(), report).bot_requirements
    assert req["channel_url"] == "https://t.me/remna_shop"
    assert req["channel_id"] is None
    assert req["channel_required"] is False
    assert any("rules" in note for note in report.notes)


def test_requirements_channel_id_kept() -> None:
    requirements = {**REQUIREMENTS, "channel_id": -1001, "channel_link": "https://t.me/x"}
    req = transform_settings(_row(requirements=requirements), MigrationReport()).bot_requirements
    assert req["channel_id"] == -1001
    assert req["channel_url"] == "https://t.me/x"


def test_referral_settings() -> None:
    ref = transform_settings(_row(), MigrationReport()).referral
    assert ref["enabled"] is True
    assert ref["max_level"] == 1
    assert ref["accrual_strategy"] is ReferralAccrualStrategy.FIRST_PAYMENT
    assert ref["reward_strategy"] is ReferralRewardStrategy.AMOUNT
    assert ref["reward_amounts"] == {"1": "30"}


def test_referral_every_payment() -> None:
    referral = {**_row()["referral"], "accrual_strategy": "ON_EACH_PAYMENT"}
    ref = transform_settings(_row(referral=referral), MigrationReport()).referral
    assert ref["accrual_strategy"] is ReferralAccrualStrategy.EVERY_PAYMENT


def test_anchor_from_default_currency() -> None:
    assert transform_settings(_row(), MigrationReport()).anchor_currency is Currency.RUB

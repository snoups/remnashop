from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Optional

from app.cli.legacy.report import MigrationReport
from app.core.db.singleton import SINGLETON_ID
from app.core.enums import (
    AccessMode,
    Currency,
    ReferralAccrualStrategy,
    ReferralRewardStrategy,
    ReferralRewardType,
)

_ACCRUAL: Final[Mapping[str, ReferralAccrualStrategy]] = {
    "ON_FIRST_PAYMENT": ReferralAccrualStrategy.FIRST_PAYMENT,
    "ON_EACH_PAYMENT": ReferralAccrualStrategy.EVERY_PAYMENT,
}
_TELEGRAM_HOSTS: Final[tuple[str, ...]] = ("t.me/", "telegram.me/", "telegram.dog/")


@dataclass(frozen=True, kw_only=True)
class SettingsRows:
    access: dict[str, Any]
    bot_requirements: dict[str, Any]
    referral: dict[str, Any]
    anchor_currency: Currency


def _channel_url(link: Optional[str]) -> Optional[str]:
    # the bot builds a url button from it, which needs a full link
    link = (link or "").strip()
    if not link:
        return None
    if link.startswith("@"):
        return f"https://t.me/{link[1:]}"
    if "://" not in link and link.startswith(_TELEGRAM_HOSTS):
        return f"https://{link}"
    return link


def transform_settings(row: Mapping[str, Any], report: MigrationReport) -> SettingsRows:
    access = row["access"]
    requirements = row["requirements"]
    referral = row["referral"]
    reward = referral["reward"]

    if requirements.get("rules_link") or requirements.get("rules_required"):
        report.notes.append(
            "settings: rules link and rules_required are not migrated, "
            "documents are managed in the dashboard"
        )

    return SettingsRows(
        access={
            "id": SINGLETON_ID,
            "mode": AccessMode(access["mode"]),
            "payments_enabled": access["purchases_allowed"],
            "registration_enabled": access["registration_allowed"],
        },
        bot_requirements={
            "id": SINGLETON_ID,
            "channel_required": requirements["channel_required"],
            "channel_id": requirements.get("channel_id") or None,
            "channel_url": _channel_url(requirements.get("channel_link")),
        },
        referral={
            "id": SINGLETON_ID,
            "enabled": referral["enable"],
            "max_level": referral["level"],
            "accrual_strategy": _ACCRUAL[referral["accrual_strategy"]],
            "reward_type": ReferralRewardType(reward["type"]),
            "reward_strategy": ReferralRewardStrategy(reward["strategy"]),
            "reward_amounts": {
                str(level): str(amount) for level, amount in reward["config"].items()
            },
        },
        anchor_currency=Currency(row["default_currency"]),
    )

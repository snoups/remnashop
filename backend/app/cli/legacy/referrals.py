from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from app.cli.legacy.report import MigrationReport
from app.core.enums import ReferralRewardType


def transform_referrals(
    referrals: Sequence[Mapping[str, Any]],
    rewards: Sequence[Mapping[str, Any]],
    *,
    user_ids: set[int],
    subscription_ids: set[int],
    report: MigrationReport,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    referral_rows: list[dict[str, Any]] = []
    for referral in sorted(referrals, key=lambda r: int(r["id"])):
        if referral["referrer_id"] not in user_ids or referral["referred_id"] not in user_ids:
            report.skip("referrals", str(referral["id"]), "user missing")
            continue
        referral_rows.append(
            {
                "id": referral["id"],
                "referrer_id": referral["referrer_id"],
                "referred_id": referral["referred_id"],
                "level": int(referral["level"]),
                "created_at": referral["created_at"],
                "updated_at": referral["updated_at"],
            }
        )

    referral_ids = {row["id"] for row in referral_rows}
    reward_rows: list[dict[str, Any]] = []
    for reward in sorted(rewards, key=lambda r: int(r["id"])):
        if not reward["is_issued"]:
            report.skip("referral_rewards", str(reward["id"]), "not issued")
            continue
        if reward["referral_id"] not in referral_ids:
            report.skip("referral_rewards", str(reward["id"]), "referral not migrated")
            continue
        reward_rows.append(
            {
                "id": reward["id"],
                "referral_id": reward["referral_id"],
                "referrer_id": reward["user_id"] if reward["user_id"] in user_ids else None,
                "payment_key": f"legacy:{reward['id']}",
                "type": ReferralRewardType(reward["type"]),
                "amount": Decimal(reward["amount"]),
                "created_at": reward["created_at"],
                "updated_at": reward["updated_at"],
            }
        )

    report.count("referrals", len(referrals), len(referral_rows))
    report.count("referral_rewards", len(rewards), len(reward_rows))
    return referral_rows, reward_rows

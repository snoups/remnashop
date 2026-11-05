from collections.abc import Mapping, Sequence
from typing import Any, Final

from app.cli.legacy.report import MigrationReport
from app.core.enums import PromocodeAvailability, PromocodeRewardType

_COPIED: Final[tuple[str, ...]] = (
    "id",
    "code",
    "is_active",
    "reward",
    "expires_at",
    "max_activations",
    "is_reusable",
    "created_at",
    "updated_at",
)


def transform_promocodes(
    promos: Sequence[Mapping[str, Any]],
    activations: Sequence[Mapping[str, Any]],
    *,
    plan_ids: set[int],
    user_ids: set[int],
    report: MigrationReport,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    promo_rows: list[dict[str, Any]] = []
    for promo in sorted(promos, key=lambda p: int(p["id"])):
        reward_type = PromocodeRewardType(promo["reward_type"])
        item = {column: promo[column] for column in _COPIED}
        item.update(
            reward_type=reward_type,
            availability=PromocodeAvailability(promo["availability"]),
        )
        if reward_type is PromocodeRewardType.SUBSCRIPTION:
            snapshot = promo["plan_snapshot"] or {}
            plan_id = snapshot.get("id")
            if plan_id in plan_ids:
                item.update(reward_plan_id=plan_id, reward_duration_days=snapshot.get("duration"))
            else:
                item["is_active"] = False
                report.notes.append(
                    f"promocodes: #{promo['id']} '{promo['code']}' rewards a missing plan, "
                    "deactivated"
                )
        promo_rows.append(item)

    promo_ids = {row["id"] for row in promo_rows}
    activation_rows: list[dict[str, Any]] = []
    for activation in sorted(activations, key=lambda a: int(a["id"])):
        if activation["user_id"] not in user_ids or activation["promocode_id"] not in promo_ids:
            report.skip("promocode_activations", str(activation["id"]), "user or promocode missing")
            continue
        activation_rows.append(
            {
                "id": activation["id"],
                "promocode_id": activation["promocode_id"],
                "user_id": activation["user_id"],
                "subscription_id": None,
                "activated_at": activation["activated_at"],
            }
        )

    report.count("promocodes", len(promos), len(promo_rows))
    report.count("promocode_activations", len(activations), len(activation_rows))
    return promo_rows, activation_rows

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final

from app.cli.legacy.report import MigrationReport
from app.core.enums import Currency

_COPIED: Final[tuple[str, ...]] = (
    "id",
    "public_code",
    "name",
    "description",
    "tag",
    "type",
    "availability",
    "traffic_limit_strategy",
    "traffic_limit",
    "device_limit",
    "allowed_telegram_ids",
    "allowed_emails",
    "internal_squads",
    "external_squad",
    "order_index",
    "is_active",
    "is_trial",
    "created_at",
    "updated_at",
)


@dataclass(frozen=True, kw_only=True)
class PlanRows:
    plans: list[dict[str, Any]]
    durations: list[dict[str, Any]]
    overrides: list[dict[str, Any]]


def transform_plans(
    plans: Sequence[Mapping[str, Any]],
    durations: Sequence[Mapping[str, Any]],
    prices: Sequence[Mapping[str, Any]],
    *,
    anchor_currency: Currency,
    report: MigrationReport,
) -> PlanRows:
    by_duration: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for price in prices:
        by_duration[int(price["plan_duration_id"])].append(price)

    duration_rows: list[dict[str, Any]] = []
    overrides: list[dict[str, Any]] = []
    unanchored = 0
    for duration in sorted(durations, key=lambda d: int(d["id"])):
        duration_id = int(duration["id"])
        base_price = Decimal("0")
        missing_anchor = True
        for price in sorted(by_duration[duration_id], key=lambda p: int(p["id"])):
            currency = Currency(price["currency"])
            if currency is anchor_currency:
                base_price, missing_anchor = Decimal(price["price"]), False
                continue
            overrides.append(
                {
                    "id": int(price["id"]),
                    "plan_duration_id": duration_id,
                    "currency": currency,
                    "price": Decimal(price["price"]),
                }
            )
        unanchored += missing_anchor
        duration_rows.append(
            {
                "id": duration_id,
                "plan_id": int(duration["plan_id"]),
                "days": duration["days"],
                "order_index": duration["order_index"],
                "base_price": base_price,
            }
        )

    plan_rows = [{c: plan[c] for c in _COPIED if c in plan} for plan in plans]
    plan_rows.sort(key=lambda p: int(p["id"]))
    report.count("plans", len(plans), len(plan_rows))
    report.count("plan_durations", len(durations), len(duration_rows))
    report.count("plan_prices", len(prices), len(prices))
    if unanchored:
        report.notes.append(
            f"plans: {unanchored} durations without an anchor currency price, "
            "base price 0 and every currency price kept as an override"
        )
    return PlanRows(plans=plan_rows, durations=duration_rows, overrides=overrides)

import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final

from app.cli.legacy.report import MigrationReport
from app.core.enums import Currency
from app.modules.plans import DEFAULT_PLAN_ICON_EMOJI_FALLBACK, DEFAULT_PLAN_ICON_EMOJI_ID

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


# joiners, variation selectors, keycap, skin tones, subdivision-flag tags
_EMOJI_PARTS: Final[frozenset[str]] = frozenset(
    "\u200d\ufe0e\ufe0f\u20e3"
    + "".join(map(chr, range(0x1F3FB, 0x1F400)))
    + "".join(map(chr, range(0xE0020, 0xE0080)))
)


def strip_leading_emoji(name: str) -> str:
    start = 0
    while start < len(name) and (
        name[start].isspace()
        or name[start] in _EMOJI_PARTS
        or unicodedata.category(name[start]) == "So"
    ):
        start += 1
    # a name of nothing but emoji stays as it was
    return name[start:] or name


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
    used_currencies: frozenset[Currency],
    report: MigrationReport,
) -> PlanRows:
    """used_currencies: what the old shop took payment in. The old bot kept a price
    in every currency, filled or not: one in a currency it never sold in is no
    owner's choice, so it goes and the default rate prices it."""
    by_duration: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for price in prices:
        by_duration[int(price["plan_duration_id"])].append(price)

    duration_rows: list[dict[str, Any]] = []
    overrides: list[dict[str, Any]] = []
    unanchored = 0
    dropped: dict[Currency, int] = defaultdict(int)
    for duration in sorted(durations, key=lambda d: int(d["id"])):
        duration_id = int(duration["id"])
        duration_prices = sorted(by_duration[duration_id], key=lambda p: int(p["id"]))
        anchor_price = next(
            (Decimal(p["price"]) for p in duration_prices if p["currency"] == anchor_currency),
            None,
        )
        missing_anchor = anchor_price is None
        base_price = anchor_price if anchor_price is not None else Decimal("0")
        for price in duration_prices:
            currency = Currency(price["currency"])
            if currency is anchor_currency:
                continue
            # without an anchor price every currency's price is all there is to keep;
            # a free trial is free everywhere, a pin on it means nothing
            if not missing_anchor and (base_price == 0 or currency not in used_currencies):
                dropped[currency] += 1
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
    renamed = 0
    for row in plan_rows:
        name = strip_leading_emoji(row["name"])
        renamed += name != row["name"]
        row["name"] = name
        row["icon_emoji_id"] = DEFAULT_PLAN_ICON_EMOJI_ID
        row["icon_emoji_fallback"] = DEFAULT_PLAN_ICON_EMOJI_FALLBACK
    report.count("plans", len(plans), len(plan_rows))
    report.count("plan_durations", len(durations), len(duration_rows))
    report.count("plan_prices", len(prices), len(prices) - sum(dropped.values()))
    if unanchored:
        report.notes.append(
            f"plans: {unanchored} durations without an anchor currency price, "
            "base price 0 and every currency price kept as an override"
        )
    if dropped:
        listed = ", ".join(f"{currency} {count}" for currency, count in sorted(dropped.items()))
        report.notes.append(
            f"plans: {sum(dropped.values())} currency prices not migrated ({listed}): "
            "a free trial's, or in a currency without an active gateway or a payment; "
            "priced by the default rate"
        )
    if renamed:
        report.notes.append(f"plans: leading emoji removed from {renamed} plan names")
    return PlanRows(plans=plan_rows, durations=duration_rows, overrides=overrides)

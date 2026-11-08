from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Final

from app.cli.legacy.panel import PanelIndex, resolve_panel_id
from app.cli.legacy.report import MigrationReport
from app.core.enums import Currency, SubscriptionStatus

_TABLE: Final[str] = "subscriptions"
_COPIED: Final[tuple[str, ...]] = (
    "id",
    "user_id",
    "status",
    "is_trial",
    "traffic_limit",
    "device_limit",
    "traffic_limit_strategy",
    "tag",
    "internal_squads",
    "external_squad",
    "expire_at",
    "url",
    "device_single_reset_at",
    "device_all_reset_at",
    "link_reset_at",
    "created_at",
    "updated_at",
)


def convert_plan_snapshot(
    old: Mapping[str, Any], *, public_code: str, price_paid: Decimal, currency: Currency
) -> dict[str, Any]:
    duration = int(old.get("duration") or 0)
    return {
        "plan_id": old["id"],
        "public_code": public_code,
        "name": old["name"],
        "price_paid": str(price_paid),
        "currency": currency.value,
        "duration_days": duration,
        "traffic_limit": old["traffic_limit"],
        "device_limit": old["device_limit"],
        "traffic_limit_strategy": str(old["traffic_limit_strategy"]),
        "is_trial": bool(old.get("is_trial")),
        "internal_squads": [str(squad) for squad in old.get("internal_squads") or []],
        "external_squad": str(old["external_squad"]) if old.get("external_squad") else None,
        "tag": old.get("tag"),
        "credit_paid": None,
        "credit_days": None,
    }


def migrated_subscription_ids(result: Sequence[Mapping[str, Any]]) -> set[int]:
    return {int(item["id"]) for item in result}


def _claim_live(
    status: SubscriptionStatus,
    sub_id: int,
    panel_id: int,
    live_panel_ids: dict[int, int],
    report: MigrationReport,
) -> SubscriptionStatus:
    if panel_id in live_panel_ids:
        report.notes.append(
            f"subscriptions #{sub_id}: deleted, panel user {panel_id} "
            f"is already used by #{live_panel_ids[panel_id]}"
        )
        return SubscriptionStatus.DELETED
    live_panel_ids[panel_id] = sub_id
    return status


def _add_notes(
    report: MigrationReport, demoted: int, unpriced: int, unknown_plans: set[int]
) -> None:
    if demoted:
        report.notes.append(f"subscriptions: {demoted} non-current subscriptions set to DELETED")
    if unpriced:
        report.notes.append(
            f"subscriptions: {unpriced} snapshots without a completed payment priced at 0"
        )
    if unknown_plans:
        report.notes.append(
            f"subscriptions: snapshot plans {sorted(unknown_plans)} not migrated, empty public code"
        )


def transform_subscriptions(
    rows: Sequence[Mapping[str, Any]],
    *,
    users: Mapping[int, Mapping[str, Any]],
    current_subscription_ids: set[int],
    index: PanelIndex,
    plan_codes: Mapping[int, str],
    last_payments: Mapping[tuple[int, int], tuple[Decimal, Currency]],
    anchor_currency: Currency,
    report: MigrationReport,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    live_panel_ids: dict[int, int] = {}
    demoted = 0
    unpriced = 0
    unknown_plans: set[int] = set()

    for row in sorted(rows, key=lambda r: int(r["id"])):
        sub_id = int(row["id"])
        user_id = int(row["user_id"])
        user = users.get(user_id)
        if user is None:
            report.skip(_TABLE, str(sub_id), f"user {user_id} not migrated")
            continue
        panel_id, reason = resolve_panel_id(
            url=row.get("url"), telegram_id=user.get("telegram_id"), user_id=user_id, index=index
        )
        if panel_id is None:
            report.skip(_TABLE, str(sub_id), f"panel user not found: {reason}")
            continue

        status = SubscriptionStatus[str(row["status"])]
        if status is not SubscriptionStatus.DELETED:
            if sub_id not in current_subscription_ids:
                status, demoted = SubscriptionStatus.DELETED, demoted + 1
            else:
                status = _claim_live(status, sub_id, panel_id, live_panel_ids, report)

        old_snapshot = row["plan_snapshot"]
        plan_id = int(old_snapshot["id"])
        public_code = plan_codes.get(plan_id)
        if public_code is None:
            public_code = ""
            unknown_plans.add(plan_id)
        paid = last_payments.get((user_id, plan_id))
        if paid is None:
            paid, unpriced = (Decimal("0"), anchor_currency), unpriced + 1
        price, currency = paid

        item = {column: row.get(column) for column in _COPIED}
        item.update(
            status=status,
            remnawave_user_id=panel_id,
            first_connected_at=index.first_connected_at.get(panel_id),
            paused_by_channel_leave=bool(row.get("disabled_by_channel_leave")),
            plan_snapshot=convert_plan_snapshot(
                old_snapshot, public_code=public_code, price_paid=price, currency=currency
            ),
        )
        result.append(item)

    report.count(_TABLE, len(rows), len(result))
    _add_notes(report, demoted, unpriced, unknown_plans)
    return result

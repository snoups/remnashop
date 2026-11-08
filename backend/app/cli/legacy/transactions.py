from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Final, Optional

from app.cli.legacy.report import MigrationReport
from app.cli.legacy.subscriptions import convert_plan_snapshot
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseChannel,
    TransactionStatus,
)

_TABLE: Final[str] = "transactions"
_CENT: Final[Decimal] = Decimal("0.01")
_COPIED: Final[tuple[str, ...]] = (
    "id",
    "user_id",
    "purchase_type",
    "is_test",
    "created_at",
    "updated_at",
)


def _status(raw: str) -> TransactionStatus:
    return TransactionStatus.PAID if raw == "COMPLETED" else TransactionStatus[raw]


def _to_anchor(
    amount: Decimal, currency: Currency, anchor: Currency, rates: Mapping[Currency, Decimal]
) -> Optional[Decimal]:
    if currency is anchor:
        return amount
    if currency not in rates or anchor not in rates:
        return None
    return (amount / rates[currency] * rates[anchor]).quantize(_CENT)


def transform_transactions(
    rows: Sequence[Mapping[str, Any]],
    *,
    plan_ids: set[int],
    subscription_ids: set[int],
    cabinet_user_ids: set[int],
    anchor_currency: Currency,
    rates: Mapping[Currency, Decimal],
    report: MigrationReport,
    plan_codes: Optional[Mapping[int, str]] = None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    unrated: list[Currency] = []
    for row in sorted(rows, key=lambda r: int(r["id"])):
        pricing = row["pricing"]
        base_price = Decimal(str(pricing["original_amount"]))
        final_price = Decimal(str(pricing["final_amount"]))
        discount_percent = int(pricing.get("discount_percent") or 0)
        currency = Currency(row["currency"])
        status = _status(str(row["status"]))

        anchor_base = _to_anchor(base_price, currency, anchor_currency, rates)
        anchor_final = _to_anchor(final_price, currency, anchor_currency, rates)
        anchor_unrated = anchor_base is None or anchor_final is None
        if anchor_unrated:
            anchor_base, anchor_final = base_price, final_price
            unrated.append(currency)

        old_snapshot = row["plan_snapshot"]
        snapshot_plan_id = int(old_snapshot["id"])
        plan_id = snapshot_plan_id if snapshot_plan_id in plan_ids else None
        public_code = (plan_codes or {}).get(snapshot_plan_id, "")

        item = {column: row[column] for column in _COPIED if column in row}
        item.update(
            plan_id=plan_id,
            plan_snapshot=convert_plan_snapshot(
                old_snapshot, public_code=public_code, price_paid=final_price, currency=currency
            ),
            previous_plan_snapshot=None,
            duration_days=int(old_snapshot.get("duration") or 0),
            currency=currency,
            channel=(
                PurchaseChannel.CABINET
                if int(row["user_id"]) in cabinet_user_ids
                else PurchaseChannel.BOT
            ),
            gateway_type=PaymentGatewayType(row["gateway_type"]),
            external_payment_id=None,
            status=status,
            base_price=base_price,
            discount_percent=discount_percent,
            discount_source=(
                DiscountSource.PERSONAL if discount_percent > 0 else DiscountSource.NONE
            ),
            discount_from_promocode=False,
            final_price=final_price,
            anchor_base_price=anchor_base,
            anchor_final_price=anchor_final,
            anchor_unrated=anchor_unrated,
            idempotency_key=str(row["payment_id"]),
            expires_at=row["created_at"],
            fulfilled_at=row["updated_at"] if status is TransactionStatus.PAID else None,
            target_subscription_id=_known(row.get("target_subscription_id"), subscription_ids),
            fulfilled_subscription_id=_known(
                row.get("fulfilled_subscription_id"), subscription_ids
            ),
        )
        result.append(item)

    report.count(_TABLE, len(rows), len(result))
    if unrated:
        currencies = ", ".join(sorted({currency.value for currency in unrated}))
        report.notes.append(
            f"transactions: anchor amounts for {len(unrated)} transactions in {currencies} "
            "equal their nominal amounts (no currency rates at migration time): "
            "check the rates in the dashboard and recalculate them there"
        )
    return result


def _known(subscription_id: Optional[int], subscription_ids: set[int]) -> Optional[int]:
    return subscription_id if subscription_id in subscription_ids else None

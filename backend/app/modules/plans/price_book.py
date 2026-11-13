from decimal import Decimal

from app.core.constants import ZERO_AMOUNT
from app.core.enums import Currency
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import PriceBookCell, PriceBookDto, PriceBookRow
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import CurrencyRateTable, PricingRepository, resolve_price


def _build_cells(
    base_price: Decimal, overrides_by_currency: dict[Currency, Decimal], table: CurrencyRateTable
) -> list[PriceBookCell]:
    cells = []
    for currency in Currency:
        override = overrides_by_currency.get(currency)
        # a free trial is free in every currency, as checkout prices it (price_for)
        amount = (
            ZERO_AMOUNT if base_price == 0 else resolve_price(base_price, currency, override, table)
        )
        cells.append(
            PriceBookCell(currency=currency, amount=amount, is_pinned=override is not None)
        )
    return cells


async def build_price_book(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
) -> PriceBookDto:
    table = await pricing_repository.get_rate_table()
    settings = await pricing_repository.get_settings()

    plans = await plan_repository.list_all()
    plan_rows = [
        PriceBookRow(
            kind="plan_duration",
            ref_id=duration.id,
            plan_id=plan.id,
            name=plan.name,
            days=duration.days,
            base_price=duration.base_price,
            cells=_build_cells(
                duration.base_price,
                {override.currency: override.price for override in duration.overrides},
                table,
            ),
        )
        for plan in plans
        for duration in plan.durations
    ]

    addons = await addon_repository.list_all()
    addon_rows = [
        PriceBookRow(
            kind="addon",
            ref_id=addon.id,
            name=addon.name,
            days=None,
            base_price=addon.base_price,
            cells=_build_cells(
                addon.base_price,
                {override.currency: override.price for override in addon.overrides},
                table,
            ),
        )
        for addon in addons
    ]

    return PriceBookDto(
        rate_table=list(table.rows.values()),
        settings=settings,
        plans=plan_rows,
        addons=addon_rows,
    )

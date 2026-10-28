from decimal import Decimal
from typing import Final, Optional

from app.core.enums import Currency, PriceAdjustScope
from app.modules.plans.dto import AddOnDto, AdjustBasePricesDto, AnchorSwitchDto, PlanDto
from app.modules.pricing import (
    BASE_PRICE_PRECISION,
    RATE_PRECISION,
    CurrencyRateTable,
    scale_base_price,
)

_ANCHOR_RATE: Final[Decimal] = Decimal("1.000000")


def adjusted_base_prices(
    adjust: AdjustBasePricesDto, plans: list[PlanDto], addons: list[AddOnDto]
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """New base prices by plan duration id and by add-on id."""
    plan_prices: dict[int, Decimal] = {}
    addon_prices: dict[int, Decimal] = {}
    selected = adjust.scope is PriceAdjustScope.SELECTED

    if adjust.scope in (PriceAdjustScope.ALL_PLANS, PriceAdjustScope.SELECTED):
        duration_ids = set(adjust.plan_duration_ids)
        plan_prices = {
            duration.id: scale_base_price(duration.base_price, adjust.factor)
            for plan in plans
            for duration in plan.durations
            if not selected or duration.id in duration_ids
        }

    if adjust.scope in (PriceAdjustScope.ALL_ADDONS, PriceAdjustScope.SELECTED):
        addon_ids = set(adjust.addon_ids)
        addon_prices = {
            addon.id: scale_base_price(addon.base_price, adjust.factor)
            for addon in addons
            if not selected or addon.id in addon_ids
        }

    return plan_prices, addon_prices


def anchor_switch(
    table: CurrencyRateTable, new_anchor: Currency, plans: list[PlanDto], addons: list[AddOnDto]
) -> AnchorSwitchDto:
    """Rates and base prices once `new_anchor` becomes the anchor; amounts keep their value."""
    factor = table.rows[new_anchor].rate
    rates = {
        currency: (row.rate / factor).quantize(RATE_PRECISION)
        for currency, row in table.rows.items()
    }
    rates[new_anchor] = _ANCHOR_RATE
    return AnchorSwitchDto(
        factor=factor,
        rates=rates,
        plan_base_prices={
            duration.id: scale_base_price(duration.base_price, factor)
            for plan in plans
            for duration in plan.durations
        },
        addon_base_prices={
            addon.id: scale_base_price(addon.base_price, factor) for addon in addons
        },
    )


def scale_unit_price(price: Optional[Decimal], factor: Decimal) -> Optional[Decimal]:
    return (price * factor).quantize(BASE_PRICE_PRECISION) if price is not None else None

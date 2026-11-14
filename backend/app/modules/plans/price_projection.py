from decimal import Decimal
from typing import Final, Optional, Sequence, Union

from app.core.enums import Currency, PinnedPriceAction, PriceAdjustMode, PriceAdjustScope
from app.modules.plans.dto import (
    AddOnDto,
    AddOnPriceOverrideDto,
    AdjustBasePricesDto,
    AnchorSwitchDto,
    BasePriceAdjustmentDto,
    PlanDto,
    PlanPriceOverrideDto,
)
from app.modules.pricing import (
    BASE_PRICE_PRECISION,
    MIN_BASE_PRICE,
    RATE_PRECISION,
    CurrencyRateTable,
    round_amount,
    scale_base_price,
)

_ANCHOR_RATE: Final[Decimal] = Decimal("1.000000")
_HUNDRED: Final[Decimal] = Decimal(100)


def adjusted_base_prices(
    adjust: AdjustBasePricesDto,
    plans: list[PlanDto],
    addons: list[AddOnDto],
    table: CurrencyRateTable,
) -> BasePriceAdjustmentDto:
    """New base prices by plan duration id and by add-on id, and the pins that change with them."""
    selected = adjust.scope is PriceAdjustScope.SELECTED
    result = BasePriceAdjustmentDto()

    if adjust.scope in (PriceAdjustScope.ALL_PLANS, PriceAdjustScope.SELECTED):
        duration_ids = set(adjust.plan_duration_ids)
        for plan in plans:
            free_trial = plan.free_trial_duration()
            for duration in plan.durations:
                # a set price or a ladder would turn a free trial into a paid one; a
                # ladder is priced by days, which an unlimited duration doesn't have
                unladdered = adjust.mode is PriceAdjustMode.LADDER and duration.days == 0
                if (
                    duration is free_trial
                    or unladdered
                    or (selected and duration.id not in duration_ids)
                ):
                    continue
                new = _new_base_price(adjust, duration.base_price, duration.days)
                result.plan_prices[duration.id] = new
                pins = _new_pins(adjust, duration.base_price, new, duration.overrides, table)
                if pins is not None:
                    result.plan_overrides[duration.id] = pins

    # a ladder is priced by days, which an add-on doesn't have
    if adjust.mode is not PriceAdjustMode.LADDER and adjust.scope in (
        PriceAdjustScope.ALL_ADDONS,
        PriceAdjustScope.SELECTED,
    ):
        addon_ids = set(adjust.addon_ids)
        for addon in addons:
            if selected and addon.id not in addon_ids:
                continue
            new = _new_base_price(adjust, addon.base_price, None)
            result.addon_prices[addon.id] = new
            pins = _new_pins(adjust, addon.base_price, new, addon.overrides, table)
            if pins is not None:
                result.addon_overrides[addon.id] = pins

    return result


def _new_base_price(adjust: AdjustBasePricesDto, price: Decimal, days: Optional[int]) -> Decimal:
    if adjust.mode is PriceAdjustMode.MULTIPLY:
        return scale_base_price(price, _required(adjust.factor))
    target = _required(adjust.price)
    if adjust.mode is PriceAdjustMode.LADDER and days is not None:
        discount = adjust.ladder_discounts.get(days, Decimal(0))
        target = target * days / adjust.ladder_base_days * (_HUNDRED - discount) / _HUNDRED
    return max(target.quantize(BASE_PRICE_PRECISION), MIN_BASE_PRICE)


def _new_pins(
    adjust: AdjustBasePricesDto,
    old_base: Decimal,
    new_base: Decimal,
    overrides: Sequence[Union[PlanPriceOverrideDto, AddOnPriceOverrideDto]],
    table: CurrencyRateTable,
) -> Optional[dict[Currency, Decimal]]:
    if not overrides or adjust.pinned is PinnedPriceAction.KEEP:
        return None
    if adjust.pinned is PinnedPriceAction.RESET:
        return {}
    if old_base == 0:
        return None
    ratio = new_base / old_base
    return {
        o.currency: round_amount(o.price * ratio, table.for_currency(o.currency), charm=False)
        for o in overrides
    }


def _required(value: Optional[Decimal]) -> Decimal:
    # the request schema pairs each mode with its value
    if value is None:
        raise ValueError("The adjust mode's value is missing")
    return value


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
    plan_prices: dict[int, Decimal] = {}
    plan_pins: dict[int, dict[Currency, Decimal]] = {}
    for plan in plans:
        for duration in plan.durations:
            plan_prices[duration.id], pins = _switched_base(
                duration.base_price, duration.overrides, new_anchor, factor
            )
            if pins is not None:
                plan_pins[duration.id] = pins
    addon_prices: dict[int, Decimal] = {}
    addon_pins: dict[int, dict[Currency, Decimal]] = {}
    for addon in addons:
        addon_prices[addon.id], pins = _switched_base(
            addon.base_price, addon.overrides, new_anchor, factor
        )
        if pins is not None:
            addon_pins[addon.id] = pins
    return AnchorSwitchDto(
        factor=factor,
        rates=rates,
        plan_base_prices=plan_prices,
        addon_base_prices=addon_prices,
        plan_overrides=plan_pins,
        addon_overrides=addon_pins,
    )


def _switched_base(
    base_price: Decimal,
    overrides: Sequence[Union[PlanPriceOverrideDto, AddOnPriceOverrideDto]],
    new_anchor: Currency,
    factor: Decimal,
) -> tuple[Decimal, Optional[dict[Currency, Decimal]]]:
    """The base price in the new anchor and, when a pin was in it, the pins left.

    The anchor column can't hold a pin, so the pinned price, which buyers paid,
    becomes the base instead.
    """
    pinned = next((o.price for o in overrides if o.currency is new_anchor), None)
    if pinned is None:
        return scale_base_price(base_price, factor), None
    rest = {o.currency: o.price for o in overrides if o.currency is not new_anchor}
    if base_price == 0:
        return base_price, rest  # a free trial stays free
    return max(pinned, MIN_BASE_PRICE), rest

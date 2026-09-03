from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Final, Optional

from app.core.enums import Currency, RoundingMode
from app.modules.pricing.dto import CurrencyRateDto, CurrencyRateTable

_HUNDRED: Final[Decimal] = Decimal("100")
_ONE_CENT: Final[Decimal] = Decimal("0.01")


def _apply_rounding(raw: Decimal, mode: RoundingMode) -> Decimal:
    if mode is RoundingMode.INTEGER:
        return raw.to_integral_value(rounding=ROUND_HALF_UP)
    return raw.quantize(_ONE_CENT, rounding=ROUND_HALF_UP)


def _apply_charm(amount: Decimal, mode: RoundingMode, charm_ending: int) -> Decimal:
    ending = Decimal(charm_ending)
    if mode is RoundingMode.INTEGER:
        period = _HUNDRED
    else:
        period = Decimal("1")
        ending = ending / _HUNDRED
    # smallest k*period + ending that is >= amount
    base = ((amount - ending) / period).to_integral_value(rounding=ROUND_CEILING) * period
    candidate = base + ending
    if candidate < amount:
        candidate = candidate + period
    return candidate


def round_amount(amount: Decimal, rate: CurrencyRateDto, *, charm: bool = True) -> Decimal:
    rounded = _apply_rounding(amount, rate.rounding_mode)
    if charm and rate.charm_ending is not None:
        rounded = _apply_charm(rounded, rate.rounding_mode, rate.charm_ending)
    rounded = max(rounded, rate.min_amount)
    return _apply_rounding(rounded, rate.rounding_mode)


def resolve_price(
    base_anchor: Decimal,
    currency: Currency,
    override: Optional[Decimal],
    rates: CurrencyRateTable,
) -> Decimal:
    rate: CurrencyRateDto = rates.for_currency(currency)

    if override is not None:
        return max(override, rate.min_amount)

    return round_amount(base_anchor * rate.rate, rate)

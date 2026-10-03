from collections.abc import Iterable
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Final, Optional, Protocol

from app.core.constants import ONE_CENT
from app.core.enums import Currency, RoundingMode
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.pricing.dto import CurrencyRateDto, CurrencyRateTable

_HUNDRED: Final[Decimal] = Decimal("100")


def _apply_rounding(raw: Decimal, mode: RoundingMode) -> Decimal:
    if mode is RoundingMode.INTEGER:
        return raw.to_integral_value(rounding=ROUND_HALF_UP)
    return raw.quantize(ONE_CENT, rounding=ROUND_HALF_UP)


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


class PriceOverride(Protocol):
    @property
    def currency(self) -> Currency: ...

    @property
    def price(self) -> Decimal: ...


def price_for(
    base_price: Decimal,
    overrides: Iterable[PriceOverride],
    currency: Currency,
    rates: CurrencyRateTable,
) -> Decimal:
    # what a plan duration or add-on costs in `currency`: its pinned price, else the converted base
    override = next((o.price for o in overrides if o.currency is currency), None)
    return resolve_price(base_price, currency, override, rates)


def convert_for_report(
    amount: Decimal, from_currency: Currency, to_currency: Currency, rates: CurrencyRateTable
) -> Decimal:
    # display only: no rounding mode or charm ending (unlike resolve_price),
    # just cut to cents, or the raw quotient ships ~28 digits
    if from_currency == to_currency:
        return amount
    anchor_amount = amount / rates.for_currency(from_currency).rate
    return (anchor_amount * rates.for_currency(to_currency).rate).quantize(
        ONE_CENT, rounding=ROUND_HALF_UP
    )


def assert_overridable_currency(currency: Currency, anchor: Currency) -> None:
    # the anchor price is the base every other currency converts from
    if currency == anchor:
        raise ValidationError(
            "Cannot override the anchor currency's price",
            code=ErrorCode.ANCHOR_PRICE_NOT_OVERRIDABLE,
        )

from decimal import Decimal

from app.core.enums import Currency, RoundingMode
from app.modules.pricing.dto import MIN_BASE_PRICE, CurrencyRateDto, CurrencyRateTable
from app.modules.pricing.resolver import price_for, resolve_price, scale_base_price


def _table(**overrides: CurrencyRateDto) -> CurrencyRateTable:
    rows = {
        Currency.USD: CurrencyRateDto(
            currency=Currency.USD,
            rate=Decimal("1"),
            rounding_mode=RoundingMode.DECIMAL_2,
            charm_ending=None,
            min_amount=Decimal("0.01"),
        ),
        Currency.RUB: CurrencyRateDto(
            currency=Currency.RUB,
            rate=Decimal("95"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("10"),
        ),
        Currency.XTR: CurrencyRateDto(
            currency=Currency.XTR,
            rate=Decimal("77"),
            rounding_mode=RoundingMode.INTEGER,
            charm_ending=None,
            min_amount=Decimal("1"),
        ),
    }
    rows.update({dto.currency: dto for dto in overrides.values()})
    return CurrencyRateTable(anchor=Currency.USD, rows=rows)


def test_anchor_currency_passthrough_with_rounding() -> None:
    assert resolve_price(Decimal("2.199"), Currency.USD, None, _table()) == Decimal("2.20")


def test_derived_integer_rounding() -> None:
    # 2.00 USD * 95 = 190
    assert resolve_price(Decimal("2.00"), Currency.RUB, None, _table()) == Decimal("190")


def test_override_wins_but_respects_min() -> None:
    assert resolve_price(Decimal("2.00"), Currency.RUB, Decimal("250"), _table()) == Decimal("250")
    assert resolve_price(Decimal("2.00"), Currency.RUB, Decimal("3"), _table()) == Decimal("10")


def test_min_amount_floor_on_derived() -> None:
    assert resolve_price(Decimal("0.05"), Currency.RUB, None, _table()) == Decimal("10")


def test_charm_ending_integer_rounds_up() -> None:
    rub = CurrencyRateDto(
        currency=Currency.RUB,
        rate=Decimal("95"),
        rounding_mode=RoundingMode.INTEGER,
        charm_ending=99,
        min_amount=Decimal("10"),
    )
    # 2.00 * 95 = 190 -> next value ending in 99 -> 199
    assert resolve_price(Decimal("2.00"), Currency.RUB, None, _table(rub=rub)) == Decimal("199")


def test_charm_ending_decimal_rounds_up() -> None:
    usd = CurrencyRateDto(
        currency=Currency.USD,
        rate=Decimal("1"),
        rounding_mode=RoundingMode.DECIMAL_2,
        charm_ending=99,
        min_amount=Decimal("0.01"),
    )
    # 2.11 -> 2.99 ; 2.99 -> 2.99
    assert resolve_price(Decimal("2.11"), Currency.USD, None, _table(usd=usd)) == Decimal("2.99")
    assert resolve_price(Decimal("2.99"), Currency.USD, None, _table(usd=usd)) == Decimal("2.99")


def test_anchor_switch_invariant() -> None:
    # Deriving RUB from a USD base equals deriving it after the base is re-expressed in RUB.
    usd_table = _table()
    base_usd = Decimal("3.49")
    from_usd = resolve_price(base_usd, Currency.RUB, None, usd_table)

    f = usd_table.rows[Currency.RUB].rate
    base_rub = (base_usd * f).quantize(Decimal("0.01"))
    rub_anchor_table = CurrencyRateTable(
        anchor=Currency.RUB,
        rows={
            Currency.RUB: CurrencyRateDto(
                currency=Currency.RUB,
                rate=Decimal("1"),
                rounding_mode=RoundingMode.INTEGER,
                charm_ending=None,
                min_amount=Decimal("10"),
            ),
            Currency.USD: CurrencyRateDto(
                currency=Currency.USD,
                rate=(Decimal("1") / f),
                rounding_mode=RoundingMode.DECIMAL_2,
                charm_ending=None,
                min_amount=Decimal("0.01"),
            ),
            Currency.XTR: usd_table.rows[Currency.XTR],
        },
    )
    from_rub = resolve_price(base_rub, Currency.RUB, None, rub_anchor_table)
    assert abs(from_usd - from_rub) <= Decimal("1")  # within integer-rounding drift


def test_scale_base_price_never_drops_below_the_minimum() -> None:
    assert scale_base_price(Decimal("5"), Decimal("0.001")) == MIN_BASE_PRICE
    assert scale_base_price(Decimal("10"), Decimal("1.5")) == Decimal("15.00")


def test_a_zero_base_price_stays_free_in_every_currency() -> None:
    assert price_for(Decimal(0), [], Currency.RUB, _table()) == Decimal(0)
    assert scale_base_price(Decimal(0), Decimal("2")) == Decimal(0)

from decimal import Decimal

import pytest

from app.core.enums import Currency, DiscountSource, PlanType, Role
from app.core.exceptions import ValidationError
from app.modules.payments.pricing import quote_price
from app.modules.plans.dto import PlanDto, PlanDurationDto, PlanPriceDto
from app.modules.users.dto import UserDto


def _plan(*, prices: dict[tuple[int, Currency], Decimal]) -> PlanDto:
    durations_by_days: dict[int, list[PlanPriceDto]] = {}
    for (days, currency), price in prices.items():
        durations_by_days.setdefault(days, []).append(PlanPriceDto(currency=currency, price=price))
    return PlanDto(
        public_code="test-plan",
        name="Test Plan",
        type=PlanType.TRAFFIC,
        traffic_limit=100,
        device_limit=3,
        durations=[
            PlanDurationDto(days=days, prices=prices_for_days)
            for days, prices_for_days in durations_by_days.items()
        ],
    )


def _user(*, personal_discount: int = 0, purchase_discount: int = 0) -> UserDto:
    return UserDto(
        name="buyer",
        role=Role.USER,
        personal_discount=personal_discount,
        purchase_discount=purchase_discount,
    )


def test_quote_price_no_discount() -> None:
    plan = _plan(prices={(30, Currency.RUB): Decimal("500")})
    quote = quote_price(plan, 30, Currency.RUB, _user())
    assert quote.base_price == Decimal("500")
    assert quote.discount_percent == 0
    assert quote.discount_source is DiscountSource.NONE
    assert quote.final_price == Decimal("500")


def test_quote_price_personal_discount_only() -> None:
    plan = _plan(prices={(30, Currency.RUB): Decimal("500")})
    quote = quote_price(plan, 30, Currency.RUB, _user(personal_discount=20))
    assert quote.discount_percent == 20
    assert quote.discount_source is DiscountSource.PERSONAL
    assert quote.final_price == Decimal("400")


def test_quote_price_purchase_discount_only() -> None:
    plan = _plan(prices={(30, Currency.RUB): Decimal("500")})
    quote = quote_price(plan, 30, Currency.RUB, _user(purchase_discount=10))
    assert quote.discount_percent == 10
    assert quote.discount_source is DiscountSource.PURCHASE
    assert quote.final_price == Decimal("450")


def test_quote_price_personal_wins_the_tie() -> None:
    plan = _plan(prices={(30, Currency.RUB): Decimal("500")})
    quote = quote_price(plan, 30, Currency.RUB, _user(personal_discount=20, purchase_discount=20))
    assert quote.discount_source is DiscountSource.PERSONAL


def test_quote_price_purchase_wins_when_larger() -> None:
    plan = _plan(prices={(30, Currency.RUB): Decimal("500")})
    quote = quote_price(plan, 30, Currency.RUB, _user(personal_discount=10, purchase_discount=30))
    assert quote.discount_source is DiscountSource.PURCHASE
    assert quote.final_price == Decimal("350")


def test_quote_price_100_percent_discount_is_free() -> None:
    plan = _plan(prices={(30, Currency.RUB): Decimal("500")})
    quote = quote_price(plan, 30, Currency.RUB, _user(personal_discount=100))
    assert quote.final_price == Decimal("0")


def test_quote_price_rub_rounds_down_to_integer() -> None:
    plan = _plan(prices={(30, Currency.RUB): Decimal("501")})
    quote = quote_price(plan, 30, Currency.RUB, _user(personal_discount=33))
    # 501 * 0.67 = 335.67 -> floor -> 335
    assert quote.final_price == Decimal("335")


def test_quote_price_usd_rounds_to_two_decimals() -> None:
    plan = _plan(prices={(30, Currency.USD): Decimal("9.99")})
    quote = quote_price(plan, 30, Currency.USD, _user(personal_discount=50))
    assert quote.final_price == Decimal("5.00")


def test_quote_price_nonzero_discount_floors_at_minimum_unit() -> None:
    plan = _plan(prices={(30, Currency.USD): Decimal("0.01")})
    quote = quote_price(plan, 30, Currency.USD, _user(personal_discount=99))
    assert quote.final_price == Decimal("0.01")


def test_quote_price_missing_duration_raises() -> None:
    plan = _plan(prices={(30, Currency.RUB): Decimal("500")})
    with pytest.raises(ValidationError):
        quote_price(plan, 60, Currency.RUB, _user())


def test_quote_price_missing_currency_for_duration_raises() -> None:
    plan = _plan(prices={(30, Currency.RUB): Decimal("500")})
    with pytest.raises(ValidationError):
        quote_price(plan, 30, Currency.USD, _user())

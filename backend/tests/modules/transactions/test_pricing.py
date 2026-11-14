from datetime import timedelta
from decimal import Decimal
from typing import Optional

import pytest

from app.core.enums import Currency, DiscountSource, PlanType, Role, RoundingMode
from app.core.exceptions import ValidationError
from app.core.utils.time import datetime_now
from app.modules.plans.dto import PlanDto, PlanDurationDto, PlanPriceOverrideDto
from app.modules.pricing.dto import CurrencyRateDto, CurrencyRateTable
from app.modules.pricing.resolver import round_amount
from app.modules.transactions.pricing import quote_price
from app.modules.users.dto import UserDto


def _plan(
    *, base_price: Decimal, overrides: Optional[dict[Currency, Decimal]] = None, days: int = 30
) -> PlanDto:
    return PlanDto(
        public_code="test-plan",
        name="Test Plan",
        type=PlanType.TRAFFIC,
        traffic_limit=100,
        device_limit=3,
        durations=[
            PlanDurationDto(
                id=1,
                days=days,
                base_price=base_price,
                overrides=[
                    PlanPriceOverrideDto(currency=currency, price=price)
                    for currency, price in (overrides or {}).items()
                ],
            )
        ],
    )


def _rates(rub_rate: Decimal = Decimal("1")) -> CurrencyRateTable:
    return CurrencyRateTable(
        anchor=Currency.USD,
        rows={
            Currency.USD: CurrencyRateDto(
                currency=Currency.USD,
                rate=Decimal("1"),
                rounding_mode=RoundingMode.DECIMAL_2,
                charm_ending=None,
                min_amount=Decimal("0.01"),
            ),
            Currency.RUB: CurrencyRateDto(
                currency=Currency.RUB,
                rate=rub_rate,
                rounding_mode=RoundingMode.INTEGER,
                charm_ending=None,
                min_amount=Decimal("1"),
            ),
            Currency.XTR: CurrencyRateDto(
                currency=Currency.XTR,
                rate=Decimal("1"),
                rounding_mode=RoundingMode.INTEGER,
                charm_ending=None,
                min_amount=Decimal("1"),
            ),
        },
    )


def _user(
    *,
    personal_discount: int = 0,
    purchase_discount: int = 0,
    personal_discount_promocode_id: Optional[int] = None,
    purchase_discount_promocode_id: Optional[int] = None,
    loyalty_discount: int = 0,
) -> UserDto:
    return UserDto(
        name="buyer",
        role=Role.USER,
        personal_discount=personal_discount,
        purchase_discount=purchase_discount,
        personal_discount_promocode_id=personal_discount_promocode_id,
        purchase_discount_promocode_id=purchase_discount_promocode_id,
        loyalty_discount=loyalty_discount,
    )


def test_quote_price_no_discount() -> None:
    plan = _plan(base_price=Decimal("500"))
    quote = quote_price(plan, 30, Currency.RUB, _user(), _rates())
    assert quote.base_price == Decimal("500")
    assert quote.discount_percent == 0
    assert quote.discount_source is DiscountSource.NONE
    assert quote.final_price == Decimal("500")


def test_quote_price_personal_discount_only() -> None:
    plan = _plan(base_price=Decimal("500"))
    quote = quote_price(plan, 30, Currency.RUB, _user(personal_discount=20), _rates())
    assert quote.discount_percent == 20
    assert quote.discount_source is DiscountSource.PERSONAL
    assert quote.final_price == Decimal("400")


def test_quote_price_purchase_discount_only() -> None:
    plan = _plan(base_price=Decimal("500"))
    quote = quote_price(plan, 30, Currency.RUB, _user(purchase_discount=10), _rates())
    assert quote.discount_percent == 10
    assert quote.discount_source is DiscountSource.PURCHASE
    assert quote.final_price == Decimal("450")


def test_quote_price_personal_wins_the_tie() -> None:
    plan = _plan(base_price=Decimal("500"))
    quote = quote_price(
        plan, 30, Currency.RUB, _user(personal_discount=20, purchase_discount=20), _rates()
    )
    assert quote.discount_source is DiscountSource.PERSONAL


def test_quote_price_purchase_wins_when_larger() -> None:
    plan = _plan(base_price=Decimal("500"))
    quote = quote_price(
        plan, 30, Currency.RUB, _user(personal_discount=10, purchase_discount=30), _rates()
    )
    assert quote.discount_source is DiscountSource.PURCHASE
    assert quote.final_price == Decimal("350")


def test_quote_price_100_percent_discount_is_free() -> None:
    plan = _plan(base_price=Decimal("500"))
    quote = quote_price(plan, 30, Currency.RUB, _user(personal_discount=100), _rates())
    assert quote.final_price == Decimal("0")


def test_quote_price_rub_rounds_half_up_to_integer() -> None:
    plan = _plan(base_price=Decimal("501"))
    quote = quote_price(plan, 30, Currency.RUB, _user(personal_discount=33), _rates())
    # 501 * 0.67 = 335.67 -> ROUND_HALF_UP -> 336
    assert quote.final_price == Decimal("336")


def test_quote_price_usd_rounds_to_two_decimals() -> None:
    plan = _plan(base_price=Decimal("9.99"))
    quote = quote_price(plan, 30, Currency.USD, _user(personal_discount=50), _rates())
    assert quote.final_price == Decimal("5.00")


def test_quote_price_nonzero_discount_floors_at_minimum_unit() -> None:
    plan = _plan(base_price=Decimal("0.01"))
    quote = quote_price(plan, 30, Currency.USD, _user(personal_discount=99), _rates())
    assert quote.final_price == Decimal("0.01")


def test_quote_price_missing_duration_raises() -> None:
    plan = _plan(base_price=Decimal("500"))
    with pytest.raises(ValidationError):
        quote_price(plan, 60, Currency.RUB, _user(), _rates())


def test_quote_price_uses_override_when_pinned() -> None:
    plan = _plan(base_price=Decimal("5"), overrides={Currency.RUB: Decimal("499")})
    quote = quote_price(plan, 30, Currency.RUB, _user(), _rates())
    assert quote.base_price == Decimal("499")


def _charm_rates() -> CurrencyRateTable:
    return CurrencyRateTable(
        anchor=Currency.USD,
        rows={
            Currency.USD: CurrencyRateDto(
                currency=Currency.USD,
                rate=Decimal("1"),
                rounding_mode=RoundingMode.DECIMAL_2,
                charm_ending=None,
                min_amount=Decimal("0.01"),
            ),
            Currency.RUB: CurrencyRateDto(
                currency=Currency.RUB,
                rate=Decimal("1"),
                rounding_mode=RoundingMode.INTEGER,
                charm_ending=99,
                min_amount=Decimal("1"),
            ),
            Currency.XTR: CurrencyRateDto(
                currency=Currency.XTR,
                rate=Decimal("1"),
                rounding_mode=RoundingMode.INTEGER,
                charm_ending=None,
                min_amount=Decimal("1"),
            ),
        },
    )


def test_quote_price_discount_is_not_negated_by_charm_ending() -> None:
    rates = _charm_rates()
    rub_rate = rates.for_currency(Currency.RUB)
    plan = _plan(base_price=Decimal("200"))
    quote = quote_price(plan, 30, Currency.RUB, _user(personal_discount=20), rates)
    assert quote.base_price == Decimal("299")  # 200 -> next value ending in 99
    assert quote.final_price < quote.base_price
    assert quote.final_price == round_amount(
        quote.base_price * Decimal("0.8"), rub_rate, charm=False
    )


def test_quote_price_zero_discount_override_survives_to_checkout_unrounded() -> None:
    rates = _charm_rates()
    plan = _plan(base_price=Decimal("5"), overrides={Currency.RUB: Decimal("100.55")})
    quote = quote_price(plan, 30, Currency.RUB, _user(), rates)
    assert quote.base_price == Decimal("100.55")
    assert quote.final_price == Decimal("100.55")


def test_quote_price_derives_from_rate() -> None:
    plan = _plan(base_price=Decimal("2"))
    rates = _rates(rub_rate=Decimal("95"))
    quote = quote_price(plan, 30, Currency.RUB, _user(), rates)
    assert quote.base_price == Decimal("190")


def test_quote_price_carries_the_winning_discounts_promocode() -> None:
    plan = _plan(base_price=Decimal("500"))
    user = _user(
        personal_discount=10,
        purchase_discount=20,
        personal_discount_promocode_id=1,
        purchase_discount_promocode_id=2,
    )
    assert quote_price(plan, 30, Currency.RUB, user, _rates()).discount_promocode_id == 2
    assert quote_price(plan, 30, Currency.RUB, _user(), _rates()).discount_promocode_id is None


def test_quote_price_converts_to_anchor_with_non_unit_rate() -> None:
    quote = quote_price(
        _plan(base_price=Decimal("10"), overrides={Currency.RUB: Decimal("905")}),
        30,
        Currency.RUB,
        _user(personal_discount=10),
        _rates(rub_rate=Decimal("90")),
    )

    assert quote.base_price == Decimal("905")
    assert quote.anchor_base_price == Decimal("10.06")
    assert quote.anchor_final_price == (quote.final_price / Decimal("90")).quantize(Decimal("0.01"))


def test_quote_price_in_anchor_currency_keeps_amounts() -> None:
    quote = quote_price(
        _plan(base_price=Decimal("4.99")), 30, Currency.USD, _user(personal_discount=20), _rates()
    )

    assert quote.anchor_base_price == quote.base_price
    assert quote.anchor_final_price == quote.final_price


def test_quote_price_full_discount_has_zero_anchor_final() -> None:
    quote = quote_price(
        _plan(base_price=Decimal("5")), 30, Currency.USD, _user(personal_discount=100), _rates()
    )

    assert quote.anchor_final_price == Decimal(0)
    assert quote.anchor_base_price == Decimal("5")


def test_quote_price_loyalty_wins_when_strictly_higher() -> None:
    quote = quote_price(
        _plan(base_price=Decimal("10")),
        30,
        Currency.USD,
        _user(personal_discount=5, loyalty_discount=7),
        _rates(),
    )

    assert (quote.discount_percent, quote.discount_source) == (7, DiscountSource.LOYALTY)
    assert quote.discount_promocode_id is None


def test_quote_price_loyalty_loses_a_tie_to_personal() -> None:
    quote = quote_price(
        _plan(base_price=Decimal("10")),
        30,
        Currency.USD,
        _user(personal_discount=7, loyalty_discount=7, personal_discount_promocode_id=3),
        _rates(),
    )

    assert (quote.discount_source, quote.discount_promocode_id) == (DiscountSource.PERSONAL, 3)


def _discounted_plan(
    percent: int, *, starts_in: Optional[int] = None, ends_in: Optional[int] = None
) -> PlanDto:
    now = datetime_now()
    return _plan(base_price=Decimal("500")).model_copy(
        update={
            "discount_percent": percent,
            "discount_starts_at": None if starts_in is None else now + timedelta(days=starts_in),
            "discount_ends_at": None if ends_in is None else now + timedelta(days=ends_in),
        }
    )


def test_quote_price_applies_plan_discount_alone() -> None:
    quote = quote_price(_discounted_plan(20), 30, Currency.RUB, _user(), _rates())
    assert quote.plan_discount_percent == 20
    assert quote.discount_source is DiscountSource.NONE
    assert quote.final_price == Decimal("400")


def test_quote_price_stacks_plan_discount_with_the_users() -> None:
    quote = quote_price(
        _discounted_plan(20), 30, Currency.RUB, _user(personal_discount=10), _rates()
    )
    # 500 * 0.8 * 0.9
    assert quote.final_price == Decimal("360")
    assert quote.plan_discount_percent == 20
    assert quote.discount_percent == 10
    assert quote.discount_source is DiscountSource.PERSONAL


def test_quote_price_skips_plan_discount_outside_its_window() -> None:
    for plan in (_discounted_plan(20, starts_in=1), _discounted_plan(20, ends_in=-1)):
        quote = quote_price(plan, 30, Currency.RUB, _user(), _rates())
        assert quote.plan_discount_percent == 0
        assert quote.final_price == Decimal("500")


def test_quote_price_applies_plan_discount_inside_its_window() -> None:
    plan = _discounted_plan(20, starts_in=-1, ends_in=1)
    quote = quote_price(plan, 30, Currency.RUB, _user(), _rates())
    assert quote.final_price == Decimal("400")


def test_quote_price_full_user_discount_is_free_on_a_discounted_plan() -> None:
    quote = quote_price(
        _discounted_plan(20), 30, Currency.RUB, _user(personal_discount=100), _rates()
    )
    assert quote.final_price == Decimal("0")


def test_quote_price_full_plan_discount_leaves_the_users_discount_unused() -> None:
    user = _user(purchase_discount=10, purchase_discount_promocode_id=7)
    quote = quote_price(_discounted_plan(100), 30, Currency.RUB, user, _rates())
    assert quote.final_price == Decimal("0")
    assert quote.discount_percent == 0
    assert quote.discount_source is DiscountSource.NONE
    assert quote.discount_promocode_id is None


def test_quote_price_free_trial_stays_free_and_spends_no_discount() -> None:
    plan = _plan(base_price=Decimal("0")).model_copy(update={"is_trial": True})
    user = _user(personal_discount=10, purchase_discount=20, purchase_discount_promocode_id=7)

    quote = quote_price(plan, 30, Currency.RUB, user, _rates())

    assert quote.final_price == Decimal("0")
    assert quote.discount_source is DiscountSource.NONE
    assert quote.discount_promocode_id is None


def test_quote_subtracts_change_credit_before_discounts() -> None:
    plan = _plan(base_price=Decimal("5000"), days=0)

    quote = quote_price(
        plan, 0, Currency.RUB, _user(loyalty_discount=10), _rates(), change_credit=Decimal("3000")
    )

    assert quote.base_price == Decimal("5000")
    assert quote.change_credit == Decimal("3000")
    assert quote.final_price == Decimal("1800")


def test_quote_change_credit_above_price_is_free() -> None:
    plan = _plan(base_price=Decimal("3000"), days=0)

    quote = quote_price(
        plan, 0, Currency.RUB, _user(purchase_discount=10), _rates(), change_credit=Decimal("5000")
    )

    assert quote.final_price == Decimal("0")
    # a one-shot discount isn't spent on a free change
    assert quote.discount_source is DiscountSource.NONE


def test_quote_change_credit_rounds_the_rest_to_the_currency() -> None:
    plan = _plan(base_price=Decimal("5000"), days=0)

    quote = quote_price(plan, 0, Currency.RUB, _user(), _rates(), change_credit=Decimal("3000.4"))

    assert quote.final_price == Decimal("2000")

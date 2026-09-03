from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Final

from app.core.enums import Currency, DiscountSource
from app.core.exceptions import ValidationError
from app.modules.payments.dto import PriceQuote
from app.modules.plans import PlanDto
from app.modules.users import UserDto

_MIN_UNIT_RUB_XTR: Final[Decimal] = Decimal("1")
_MIN_UNIT_OTHER: Final[Decimal] = Decimal("0.01")


def _apply_currency_rules(amount: Decimal, currency: Currency) -> Decimal:
    if currency in (Currency.RUB, Currency.XTR):
        amount = amount.to_integral_value(rounding=ROUND_DOWN)
        min_amount = _MIN_UNIT_RUB_XTR
    else:
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        min_amount = _MIN_UNIT_OTHER

    if amount < min_amount:
        amount = min_amount
    return amount


def _base_price(plan: PlanDto, duration_days: int, currency: Currency) -> Decimal:
    for duration in plan.durations:
        if duration.days != duration_days:
            continue
        for price in duration.prices:
            if price.currency is currency:
                return price.price
        raise ValidationError(
            f"Plan '{plan.public_code}' has no price for currency '{currency.value}' "
            f"at duration '{duration_days}' days"
        )
    raise ValidationError(f"Plan '{plan.public_code}' has no duration of '{duration_days}' days")


def _effective_discount(user: UserDto) -> tuple[int, DiscountSource]:
    personal = user.personal_discount
    purchase = user.purchase_discount
    percent = min(max(personal, purchase), 100)
    if percent == 0:
        return 0, DiscountSource.NONE
    if personal >= purchase:
        return percent, DiscountSource.PERSONAL
    return percent, DiscountSource.PURCHASE


def quote_price(plan: PlanDto, duration_days: int, currency: Currency, user: UserDto) -> PriceQuote:
    base_price = _base_price(plan, duration_days, currency)
    discount_percent, discount_source = _effective_discount(user)

    if discount_percent >= 100:
        return PriceQuote(
            base_price=base_price,
            discount_percent=100,
            discount_source=discount_source,
            final_price=Decimal(0),
        )

    discounted = base_price * (Decimal(100) - Decimal(discount_percent)) / Decimal(100)
    final_price = _apply_currency_rules(discounted, currency)

    return PriceQuote(
        base_price=base_price,
        discount_percent=discount_percent,
        discount_source=discount_source,
        final_price=final_price,
    )

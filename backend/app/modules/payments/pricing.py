from decimal import Decimal

from app.core.enums import Currency, DiscountSource
from app.core.exceptions import ValidationError
from app.modules.payments.dto import PriceQuote
from app.modules.plans import PlanDto
from app.modules.pricing import CurrencyRateTable, resolve_price, round_amount
from app.modules.users import UserDto


def _base_price(
    plan: PlanDto, duration_days: int, currency: Currency, rates: CurrencyRateTable
) -> Decimal:
    for duration in plan.durations:
        if duration.days != duration_days:
            continue
        override = next((o.price for o in duration.overrides if o.currency is currency), None)
        return resolve_price(duration.base_price, currency, override, rates)
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


def quote_price(
    plan: PlanDto, duration_days: int, currency: Currency, user: UserDto, rates: CurrencyRateTable
) -> PriceQuote:
    base_price = _base_price(plan, duration_days, currency, rates)
    discount_percent, discount_source = _effective_discount(user)

    if discount_percent >= 100:
        return PriceQuote(
            base_price=base_price,
            discount_percent=100,
            discount_source=discount_source,
            final_price=Decimal(0),
        )

    if discount_percent == 0:
        final_price = base_price
    else:
        discounted = base_price * (Decimal(100) - Decimal(discount_percent)) / Decimal(100)
        final_price = round_amount(discounted, rates.for_currency(currency), charm=False)

    return PriceQuote(
        base_price=base_price,
        discount_percent=discount_percent,
        discount_source=discount_source,
        final_price=final_price,
    )

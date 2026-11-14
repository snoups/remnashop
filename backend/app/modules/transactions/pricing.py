from decimal import Decimal
from typing import Optional

from app.core.constants import ZERO_AMOUNT
from app.core.enums import Currency, DiscountSource
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.utils.time import datetime_now
from app.modules.plans import PlanDto
from app.modules.pricing import (
    CurrencyRateDto,
    CurrencyRateTable,
    apply_discounts,
    convert_for_report,
    price_for,
    round_amount,
)
from app.modules.subscriptions import SubscriptionDto
from app.modules.transactions.dto import PriceQuote
from app.modules.users import UserDto


def _base_price(
    plan: PlanDto, duration_days: int, currency: Currency, rates: CurrencyRateTable
) -> Decimal:
    for duration in plan.sellable_durations():
        if duration.days != duration_days:
            continue
        return price_for(duration.base_price, duration.overrides, currency, rates)
    raise ValidationError(
        f"Plan has no duration of '{duration_days}' days",
        code=ErrorCode.PLAN_DURATION_NOT_FOUND,
    )


def _effective_discount(user: UserDto) -> tuple[int, DiscountSource, Optional[int]]:
    # (percent, source, promocode that set it); a tie goes to the earlier source
    candidates = (
        (user.personal_discount, DiscountSource.PERSONAL, user.personal_discount_promocode_id),
        (user.purchase_discount, DiscountSource.PURCHASE, user.purchase_discount_promocode_id),
        (user.loyalty_discount, DiscountSource.LOYALTY, None),
    )
    percent, source, promocode_id = max(candidates, key=lambda candidate: candidate[0])
    if percent <= 0:
        return 0, DiscountSource.NONE, None
    return min(percent, 100), source, promocode_id


def _after_credit(base_price: Decimal, credit: Decimal, rate: CurrencyRateDto) -> Decimal:
    if credit <= 0:
        return base_price
    rest = base_price - credit
    return round_amount(rest, rate, charm=False) if rest > 0 else ZERO_AMOUNT


def quote_price(
    plan: PlanDto,
    duration_days: int,
    currency: Currency,
    user: UserDto,
    rates: CurrencyRateTable,
    *,
    change_credit: Decimal = ZERO_AMOUNT,
) -> PriceQuote:
    base_price = _base_price(plan, duration_days, currency, rates)
    rate = rates.for_currency(currency)
    # what the plan being changed was paid comes off first, discounts apply to the rest
    payable = _after_credit(base_price, change_credit, rate)
    plan_discount_percent = plan.active_discount(datetime_now())
    if payable == 0 or plan_discount_percent >= 100:
        # already free: a one-shot purchase discount must not be spent on it
        discount_percent, discount_source, discount_promocode_id = 0, DiscountSource.NONE, None
    else:
        discount_percent, discount_source, discount_promocode_id = _effective_discount(user)

    # applied one after the other: -20% and -10% make -28%, never past 100%
    final_price = apply_discounts(payable, rate, plan_discount_percent, discount_percent)

    return PriceQuote(
        base_price=base_price,
        discount_percent=discount_percent,
        discount_source=discount_source,
        final_price=final_price,
        # the credit isn't a discount: reports take discounts off what was left to pay
        anchor_base_price=convert_for_report(payable, currency, rates.anchor, rates),
        anchor_final_price=convert_for_report(final_price, currency, rates.anchor, rates),
        discount_promocode_id=discount_promocode_id,
        plan_discount_percent=plan_discount_percent,
        change_credit=change_credit,
    )


def change_credit_for(
    target: SubscriptionDto, duration_days: int, currency: Currency, rates: CurrencyRateTable
) -> Decimal:
    """What a change from `target` to a plan's `duration_days` takes off the price: all
    that was paid for an unlimited subscription moving to another unlimited plan."""
    if duration_days != 0 or not target.is_unlimited or target.is_trial:
        return ZERO_AMOUNT
    snapshot = target.plan_snapshot
    return rates.convert(snapshot.effective_credit_paid, snapshot.currency, currency)

from datetime import datetime, timedelta
from decimal import Decimal

from app.core.enums import Currency, Role
from app.core.utils.time import datetime_now
from app.modules.pricing import CurrencyRateTable
from app.modules.users import UserRepository


async def resolve_since(user_repository: UserRepository, days: int) -> datetime:
    today_start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)
    today = today_start.date()
    if days == 0:
        first_registration = await user_repository.earliest_registration(Role.USER)
        start_date = first_registration or today
    else:
        start_date = today - timedelta(days=days - 1)
    return today_start - timedelta(days=(today - start_date).days)


def convert_amount(
    amount: Decimal, from_currency: Currency, to_currency: Currency, rates: CurrencyRateTable
) -> Decimal:
    # Display-only reporting conversion, same shape as overview's own
    # _convert() -- not app.modules.pricing.resolve_price, no rounding/charm-
    # ending rules apply to a report number.
    if from_currency == to_currency:
        return amount
    anchor_amount = amount / rates.for_currency(from_currency).rate
    return anchor_amount * rates.for_currency(to_currency).rate

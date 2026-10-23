from decimal import ROUND_HALF_UP, Decimal

from app.core.constants import ONE_CENT


def round_cents(value: Decimal) -> Decimal:
    return value.quantize(ONE_CENT, rounding=ROUND_HALF_UP)

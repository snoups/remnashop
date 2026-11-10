from decimal import ROUND_HALF_UP, Decimal

from babel import Locale as BabelLocale
from babel.numbers import format_currency

from app.core.constants import ONE_CENT
from app.core.enums import Currency, Locale


def round_cents(value: Decimal) -> Decimal:
    return value.quantize(ONE_CENT, rounding=ROUND_HALF_UP)


def format_money(amount: str, currency: str, locale: Locale) -> str:
    value = Decimal(amount)
    # babel knows no symbol for Telegram Stars, and they are always whole
    if currency == Currency.XTR:
        return f"{int(value)} {Currency.XTR.symbol}"
    if value != value.to_integral_value():
        return format_currency(value, currency, locale=locale.value)
    # the locale's own pattern without the cents: "1 500 ₽", "$12"
    pattern = BabelLocale.parse(locale.value).currency_formats["standard"].pattern
    return format_currency(
        value,
        currency,
        format=pattern.replace(".00", ""),
        locale=locale.value,
        currency_digits=False,
    )

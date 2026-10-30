from decimal import Decimal
from typing import Union

from babel import Locale as BabelLocale
from babel.numbers import format_currency

from app.core.enums import Currency, Locale


def _money(amount: str, currency: str, locale: Locale) -> str:
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


def customer_render_args(
    args: dict[str, Union[str, int]], locale: Locale
) -> dict[str, Union[str, int]]:
    """What the templates print but the feed does not store: it is rendered per reader."""
    rendered = dict(args)
    hours = args.get("hours")
    if isinstance(hours, int):
        # a plain number, so the plural selectors still match
        rendered["span_unit"], rendered["span"] = (
            ("day", hours // 24) if hours >= 24 else ("hour", hours)
        )
    if "amount" in args and "currency" in args:
        rendered["money"] = _money(str(args["amount"]), str(args["currency"]), locale)
    return rendered

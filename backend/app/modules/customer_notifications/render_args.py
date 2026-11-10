from typing import Union

from app.core.enums import Locale
from app.core.utils.money import format_money


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
        rendered["money"] = format_money(str(args["amount"]), str(args["currency"]), locale)
    return rendered

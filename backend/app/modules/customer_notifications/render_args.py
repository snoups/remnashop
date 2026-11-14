from typing import Optional, Union

from app.core.enums import Locale
from app.core.utils.money import format_money
from app.modules.subscriptions import SubscriptionGrantedEvent


def customer_render_args(
    args: dict[str, Union[str, int]], locale: Locale, event_type: Optional[str] = None
) -> dict[str, Union[str, int]]:
    """What the templates print but the feed does not store: it is rendered per reader."""
    rendered = dict(args)
    hours = args.get("hours")
    if isinstance(hours, int):
        # a plain number, so the plural selectors still match
        rendered["span_unit"], rendered["span"] = (
            ("day", hours // 24) if hours >= 24 else ("hour", hours)
        )
    if event_type == SubscriptionGrantedEvent.__name__:
        # a feed row stored before the plan name was has none
        rendered["has_plan_name"] = "yes" if args.get("plan_name") else "no"
    if "amount" in args and "currency" in args:
        rendered["money"] = format_money(str(args["amount"]), str(args["currency"]), locale)
    return rendered

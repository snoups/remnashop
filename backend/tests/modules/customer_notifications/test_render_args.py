from decimal import Decimal
from typing import Union

import pytest
from babel.numbers import format_currency

from app.core.enums import Locale
from app.modules.customer_notifications.render_args import customer_render_args


@pytest.mark.parametrize(
    ("hours", "span", "unit"), [(1, 1, "hour"), (23, 23, "hour"), (24, 1, "day"), (48, 2, "day")]
)
def test_hours_become_a_span(hours: int, span: int, unit: str) -> None:
    args = customer_render_args({"hours": hours}, Locale.RU)

    assert (args["span"], args["span_unit"], args["hours"]) == (span, unit, hours)


def test_whole_rubles_have_no_kopecks() -> None:
    args = customer_render_args({"amount": "1500.00", "currency": "RUB"}, Locale.RU)

    # babel's own spacing, as in its "1\xa0500,00\xa0₽" for Decimal("1500"), minus the kopecks
    assert format_currency(Decimal("1500"), "RUB", locale="ru") == "1\xa0500,00\xa0₽"
    assert args["money"] == "1\xa0500\xa0₽"


@pytest.mark.parametrize(
    ("amount", "currency", "locale", "money"),
    [
        ("1499.50", "RUB", Locale.RU, "1\xa0499,50\xa0₽"),
        ("12.00", "USD", Locale.EN, "$12"),
        ("12.5", "USD", Locale.EN, "$12.50"),
        ("12", "XTR", Locale.RU, "12 ★"),
        ("12", "XTR", Locale.EN, "12 ★"),
    ],
)
def test_money_in_the_reader_locale(amount: str, currency: str, locale: Locale, money: str) -> None:
    args = customer_render_args({"amount": amount, "currency": currency, "order_id": 3}, locale)

    assert args["money"] == money


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"duration_days": 30},
        {"reward_type": "POINTS", "amount": 5},
        {"addon_type": "TRAFFIC", "amount": 10},
        {"browser": "Firefox", "ip": "1.2.3.4"},
    ],
)
def test_other_args_are_left_alone(args: dict[str, Union[str, int]]) -> None:
    assert customer_render_args(args, Locale.EN) == args


def test_stored_args_are_not_mutated() -> None:
    args: dict[str, Union[str, int]] = {"hours": 48}

    customer_render_args(args, Locale.EN)

    assert args == {"hours": 48}

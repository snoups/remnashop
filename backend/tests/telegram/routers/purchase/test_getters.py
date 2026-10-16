from typing import Any
from unittest.mock import AsyncMock, MagicMock

from app.core.constants import USER_KEY
from app.core.enums import Currency, Locale
from app.modules.subscriptions import PlanCatalogDto
from app.telegram.routers.purchase.getters import (
    confirm_getter,
    duration_getter,
    method_getter,
    plan_getter,
)
from tests.telegram.routers.purchase.test_handlers import _plan


def _get(key: str, **kwargs: Any) -> str:
    return f"{key}{kwargs}" if kwargs else key


def _manager(dialog_data: dict) -> MagicMock:
    manager = MagicMock()
    manager.middleware_data = {USER_KEY: MagicMock(id=1, language=Locale.EN)}
    manager.dialog_data = dialog_data
    return manager


def _i18n() -> MagicMock:
    i18n = MagicMock()
    i18n.get_translator_by_locale.return_value = MagicMock(get=_get)
    return i18n


async def test_plan_list_hides_the_current_plan_on_change() -> None:
    catalog = PlanCatalogDto(plans=[_plan(id=10), _plan(id=11)], anchor_currency=Currency.RUB)

    data = await plan_getter.__dishka_orig_func__(
        _manager({"purchase_type": "CHANGE", "current_plan_id": 10}),
        list_active_plans=AsyncMock(return_value=catalog),
        i18n=_i18n(),
    )

    assert data["plans"] == [{"id": 11, "label": "Plan 11"}]


async def test_duration_labels_price_in_the_anchor_currency() -> None:
    catalog = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.USD)

    data = await duration_getter.__dishka_orig_func__(
        _manager({"plan_id": 10}),
        list_active_plans=AsyncMock(return_value=catalog),
        i18n=_i18n(),
    )

    assert data["durations"] == [
        {
            "days": 30,
            "label": _get("btn-purchase.duration", days=30, price="2.50", currency_symbol="$"),
        }
    ]


async def test_duration_window_of_a_gone_plan_says_so() -> None:
    catalog = PlanCatalogDto(plans=[], anchor_currency=Currency.RUB)

    data = await duration_getter.__dishka_orig_func__(
        _manager({"plan_id": 10}),
        list_active_plans=AsyncMock(return_value=catalog),
        i18n=_i18n(),
    )

    assert data["durations"] == []
    assert data["window_text"] == "msg-window-gone"


_PRICED = {
    "prices": {"RUB": "199", "XTR": "100", "USD": "2.5"},
    "methods": [
        {"gateway_type": "YOOKASSA", "currency": "RUB"},
        {"gateway_type": "TELEGRAM_STARS", "currency": "XTR"},
    ],
}


async def test_method_labels_price_in_each_method_currency() -> None:
    data = await method_getter.__dishka_orig_func__(_manager(dict(_PRICED)), i18n=_i18n())

    assert data["methods"] == [
        {
            "id": "YOOKASSA",
            "label": _get(
                "btn-purchase.method",
                gateway="gateway-name.YOOKASSA",
                price="199",
                currency_symbol="₽",
            ),
        },
        {
            "id": "TELEGRAM_STARS",
            "label": _get(
                "btn-purchase.method",
                gateway="gateway-name.TELEGRAM_STARS",
                price="100",
                currency_symbol="★",
            ),
        },
    ]


async def test_confirm_shows_the_chosen_method_price() -> None:
    dialog_data = {
        **_PRICED,
        "plan_name": "Plan 10",
        "duration_days": 30,
        "currency": "USD",
        "gateway_type": "CRYPTOMUS",
    }

    data = await confirm_getter.__dishka_orig_func__(_manager(dialog_data), i18n=_i18n())

    assert data["window_text"] == _get(
        "msg-purchase-confirm",
        plan_name="Plan 10",
        duration_days=30,
        price="2.50",
        currency_symbol="$",
        method="gateway-name.CRYPTOMUS",
    )

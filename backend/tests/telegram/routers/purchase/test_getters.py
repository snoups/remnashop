from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from remnapy.enums import TrafficLimitStrategy

from app.core.constants import ICON_ID_KEY_SUFFIX, USER_KEY
from app.core.enums import Currency, DiscountSource, Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.subscriptions import PlanCatalogDto, SubscriptionDto
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY
from app.telegram.routers.purchase.getters import (
    _plan_title,
    confirm_getter,
    duration_getter,
    method_getter,
    plan_getter,
)
from tests.modules.subscriptions.factories import make_subscription_dto
from tests.telegram.routers.purchase.test_handlers import _plan


def _get(key: str, **kwargs: Any) -> str:
    if key.endswith(ICON_ID_KEY_SUFFIX):
        return ""  # no premium icons: the glyph rides in the label
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

    assert data["plans"] == [{"id": 11, "label": "Plan 11", "icon_id": None, "badge": ""}]


def _quote(price: str, percent: int = 0, source: DiscountSource = DiscountSource.NONE) -> AsyncMock:
    return AsyncMock(
        return_value=MagicMock(
            final_price=Decimal(price), discount_percent=percent, discount_source=source
        )
    )


async def _durations(
    dialog_data: dict, catalog: PlanCatalogDto, quote: AsyncMock, owned: list | None = None
) -> dict:
    return await duration_getter.__dishka_orig_func__(
        _manager(dialog_data),
        list_active_plans=AsyncMock(return_value=catalog),
        list_own_subscriptions=AsyncMock(return_value=owned or []),
        quote_checkout=quote,
        i18n=_i18n(),
    )


async def test_duration_labels_carry_the_quoted_price_and_the_period() -> None:
    catalog = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.USD)

    data = await _durations(
        {"plan_id": 10, "purchase_type": "NEW"},
        catalog,
        _quote("2.25", 10, DiscountSource.PERSONAL),
    )

    assert data["durations"] == [
        {
            "days": 30,
            "label": _get(
                "btn-purchase.duration",
                period=_get("time-unit.month", value=1),
                price="2.25",
                currency_symbol="$",
            ),
        }
    ]
    assert "frg-purchase-discount" in data["window_text"]
    assert "'percent': 10" in data["window_text"]
    assert data["back_text"].text.endswith(" btn-purchase.back-plans")


async def test_duration_falls_back_to_the_list_price_when_the_quote_fails() -> None:
    catalog = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.USD)
    quote = AsyncMock(side_effect=ValidationError("x", code=ErrorCode.PLAN_NOT_FOUND))

    data = await _durations({"plan_id": 10, "purchase_type": "NEW"}, catalog, quote)

    assert "'price': '2.50'" in data["durations"][0]["label"]
    assert "frg-purchase-discount" not in data["window_text"]


async def test_renewal_shows_the_plans_limits_and_notes_its_edit() -> None:
    catalog = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.USD)
    renewed = MagicMock(
        id=3,
        plan_snapshot=MagicMock(
            traffic_limit=50, device_limit=2, traffic_limit_strategy=TrafficLimitStrategy.NO_RESET
        ),
    )

    data = await _durations(
        {"plan_id": 10, "purchase_type": "RENEW", SELECTED_SUBSCRIPTION_KEY: 3},
        catalog,
        _quote("2.5"),
        [renewed],
    )

    # the plan's own limits: a paid renewal moves the subscription to them
    assert "'traffic_limit': 0" in data["window_text"]
    assert "frg-purchase-plan-changed" in data["window_text"]
    assert data["back_text"].text.endswith(" btn-back.general")


async def test_renewal_of_an_unedited_plan_has_no_note() -> None:
    catalog = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.USD)
    renewed = MagicMock(
        id=3,
        plan_snapshot=MagicMock(
            traffic_limit=0, device_limit=0, traffic_limit_strategy=TrafficLimitStrategy.NO_RESET
        ),
    )

    data = await _durations(
        {"plan_id": 10, "purchase_type": "RENEW", SELECTED_SUBSCRIPTION_KEY: 3},
        catalog,
        _quote("2.5"),
        [renewed],
    )

    assert "frg-purchase-plan-changed" not in data["window_text"]


async def test_duration_window_of_a_gone_plan_says_so() -> None:
    catalog = PlanCatalogDto(plans=[], anchor_currency=Currency.RUB)

    data = await _durations({"plan_id": 10, "purchase_type": "NEW"}, catalog, _quote("1"))

    assert data["durations"] == []
    assert data["window_text"] == "msg-window-gone"


_PRICED = {
    "plan_id": 10,
    "purchase_type": "NEW",
    "duration_days": 30,
    "prices": {"RUB": "199", "XTR": "100", "USD": "2.5"},
    "methods": [
        {"gateway_type": "YOOKASSA", "currency": "RUB"},
        {"gateway_type": "TELEGRAM_STARS", "currency": "XTR"},
    ],
}
_CATALOG = PlanCatalogDto(plans=[_plan(id=10)], anchor_currency=Currency.RUB)


async def test_method_labels_price_in_each_method_currency() -> None:
    data = await method_getter.__dishka_orig_func__(
        _manager(dict(_PRICED)),
        list_active_plans=AsyncMock(return_value=_CATALOG),
        i18n=_i18n(),
    )

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
    assert "frg-purchase-plan" in data["window_text"]
    assert data["back_text"].text.endswith(" btn-purchase.back-duration")


async def _confirm(dialog_data: dict, owned: Optional[list[SubscriptionDto]] = None) -> dict:
    return await confirm_getter.__dishka_orig_func__(
        _manager(dialog_data),
        list_active_plans=AsyncMock(return_value=_CATALOG),
        list_own_subscriptions=AsyncMock(return_value=owned or []),
        list_visible_legal_documents=MagicMock(execute=AsyncMock(return_value=[])),
        i18n=_i18n(),
    )


async def test_confirm_shows_the_chosen_method_price() -> None:
    data = await _confirm(
        {**_PRICED, "plan_name": "Plan 10", "currency": "USD", "gateway_type": "CRYPTOMUS"}
    )

    text = data["window_text"]
    assert "'purchase_type': 'NEW'" in text
    assert "'price': '2.50'" in text
    assert "'method': 'gateway-name.CRYPTOMUS'" in text
    assert "frg-purchase-type-notice" not in text
    assert data["back_text"].text.endswith(" btn-purchase.back-method")


async def test_confirm_of_a_change_warns_about_the_replacement() -> None:
    data = await _confirm(
        {
            **_PRICED,
            "purchase_type": "CHANGE",
            "plan_name": "Plan 10",
            "currency": "RUB",
            "gateway_type": "YOOKASSA",
            "method_skipped": True,
        }
    )

    assert "frg-purchase-type-notice{'purchase_type': 'CHANGE'}" in data["window_text"]
    assert data["back_text"].text.endswith(" btn-purchase.back-duration")


@pytest.mark.parametrize(
    ("target_year", "days", "kind"),
    [(2099, 0, "credit"), (2027, 0, "no_carry"), (2099, 30, "no_carry")],
)
async def test_confirm_of_an_unlimited_change_says_what_carries_over(
    target_year: int, days: int, kind: str
) -> None:
    target = make_subscription_dto(id=5, expire_at=datetime(target_year, 1, 1, tzinfo=timezone.utc))

    data = await _confirm(
        {
            **_PRICED,
            "purchase_type": "CHANGE",
            "duration_days": days,
            "plan_name": "Plan 10",
            "currency": "RUB",
            "gateway_type": "YOOKASSA",
            SELECTED_SUBSCRIPTION_KEY: 5,
        },
        owned=[target],
    )

    assert f"frg-purchase-change-unlimited-notice{{'kind': '{kind}'}}" in data["window_text"]
    assert "frg-purchase-type-notice" not in data["window_text"]


async def test_plan_buttons_carry_the_custom_emoji_or_lead_with_the_glyph() -> None:
    with_emoji = replace(
        _plan(id=10), icon_emoji_id="5429613693287578957", icon_emoji_fallback="📦"
    )
    glyph_only = replace(_plan(id=11), icon_emoji_fallback="⭐")
    catalog = PlanCatalogDto(plans=[with_emoji, glyph_only], anchor_currency=Currency.RUB)

    data = await plan_getter.__dishka_orig_func__(
        _manager({"purchase_type": "NEW"}),
        list_active_plans=AsyncMock(return_value=catalog),
        i18n=_i18n(),
    )

    assert data["plans"] == [
        {"id": 10, "label": "Plan 10", "icon_id": "5429613693287578957", "badge": ""},
        {"id": 11, "label": "⭐ Plan 11", "icon_id": None, "badge": ""},
    ]


def test_plan_title_renders_the_icon_before_an_escaped_name() -> None:
    assert _plan_title("A<B", "123", "📦") == '<tg-emoji emoji-id="123">📦</tg-emoji> A&lt;B'
    assert _plan_title("A<B", None, "⭐") == "⭐ A&lt;B"
    assert _plan_title("A<B", None, None) == "A&lt;B"

from decimal import Decimal
from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub, TranslatorRunner

from app.core.constants import USER_KEY
from app.core.enums import Currency, PurchaseType
from app.modules.subscriptions import ListActivePlansUseCase
from app.modules.users import UserDto
from app.telegram.dialogs.rendering import label_with_icon, render_window_text
from app.telegram.i18n import get_translator
from app.telegram.routers.purchase.handlers import (
    PAYMENT_URL_KEY,
    format_price,
    plans_for,
    price_in,
    selected_plan,
)


def _price(prices: dict[str, str], currency: str) -> str:
    return format_price(Decimal(prices[currency]))


def _runner(dialog_manager: DialogManager, i18n: TranslatorHub) -> TranslatorRunner:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    return get_translator(i18n, user)


@inject
async def plan_getter(
    dialog_manager: DialogManager,
    list_active_plans: FromDishka[ListActivePlansUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    runner = _runner(dialog_manager, i18n)
    data = dialog_manager.dialog_data
    catalog = await list_active_plans(dialog_manager.middleware_data[USER_KEY])
    plans = plans_for(PurchaseType(data["purchase_type"]), catalog, data.get("current_plan_id"))
    return {
        "window_text": render_window_text(runner, "msg-purchase-plan"),
        "plans": [{"id": plan.id, "label": plan.name} for plan in plans],
        "back_text": label_with_icon(runner, "btn-back.general"),
    }


@inject
async def duration_getter(
    dialog_manager: DialogManager,
    list_active_plans: FromDishka[ListActivePlansUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    runner = _runner(dialog_manager, i18n)
    catalog = await list_active_plans(dialog_manager.middleware_data[USER_KEY])
    plan = selected_plan(catalog, dialog_manager.dialog_data)
    durations = plan.durations if plan is not None else []
    return {
        "window_text": render_window_text(runner, "msg-purchase-duration", plan_name=plan.name)
        if plan is not None
        # dropped from the catalog while the window stayed open
        else render_window_text(runner, "msg-window-gone"),
        "durations": [
            {
                "days": duration.days,
                "label": runner.get(
                    "btn-purchase.duration",
                    days=duration.days,
                    price=format_price(price_in(duration, catalog.anchor_currency)),
                    currency_symbol=catalog.anchor_currency.symbol,
                ),
            }
            for duration in durations
        ],
        "back_text": label_with_icon(runner, "btn-back.general"),
    }


@inject
async def method_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    runner = _runner(dialog_manager, i18n)
    data = dialog_manager.dialog_data
    return {
        "window_text": render_window_text(runner, "msg-purchase-method"),
        "methods": [
            {
                "id": method["gateway_type"],
                "label": runner.get(
                    "btn-purchase.method",
                    gateway=runner.get(f"gateway-name.{method['gateway_type']}"),
                    price=_price(data["prices"], method["currency"]),
                    currency_symbol=Currency(method["currency"]).symbol,
                ),
            }
            for method in data.get("methods", [])
        ],
        "back_text": label_with_icon(runner, "btn-back.general"),
    }


@inject
async def confirm_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    runner = _runner(dialog_manager, i18n)
    data = dialog_manager.dialog_data
    return {
        "window_text": render_window_text(
            runner,
            "msg-purchase-confirm",
            plan_name=data["plan_name"],
            duration_days=data["duration_days"],
            price=_price(data["prices"], data["currency"]),
            currency_symbol=Currency(data["currency"]).symbol,
            method=runner.get(f"gateway-name.{data['gateway_type']}"),
        ),
        "pay_text": label_with_icon(runner, "btn-purchase.pay"),
        "back_text": label_with_icon(runner, "btn-back.general"),
    }


@inject
async def pay_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    runner = _runner(dialog_manager, i18n)
    return {
        "window_text": render_window_text(runner, "msg-purchase-pay"),
        "payment_url": dialog_manager.dialog_data[PAYMENT_URL_KEY],
        "pay_text": label_with_icon(runner, "btn-purchase.go-to-payment"),
        "menu_text": label_with_icon(runner, "btn-purchase.menu"),
    }

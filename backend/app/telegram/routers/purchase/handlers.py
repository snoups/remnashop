from decimal import Decimal
from typing import Any, Final, Optional

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Data, DialogManager, StartMode
from aiogram_dialog.widgets.kbd import Button, Keyboard
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub

from app.core.constants import USER_KEY
from app.core.enums import Currency, PaymentGatewayType, PurchaseChannel, PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.subscriptions import (
    CatalogDurationDto,
    CatalogPlanDto,
    ListActivePlansDto,
    ListActivePlansUseCase,
    ListOwnSubscriptionsUseCase,
    PlanCatalogDto,
    SubscriptionDto,
)
from app.modules.transactions import (
    CreateCheckoutDto,
    CreateCheckoutUseCase,
    ListPaymentMethodsUseCase,
    PaymentMethodDto,
)
from app.modules.users import UserDto
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY, selected_subscription_id
from app.telegram.i18n import get_translator
from app.telegram.states import MainMenu, Purchase

PAYMENT_URL_KEY: Final[str] = "payment_url"
PLAN_CODE_KEY: Final[str] = "plan_code"
RETRY_PLAN_KEY: Final[str] = "retry_plan_id"
RETRY_DURATION_KEY: Final[str] = "retry_duration_days"
# the link offered renew-or-new, so its back buttons return there
LINK_CHOICE_KEY: Final[str] = "link_choice"
_ERROR_KEYS: Final[dict[ErrorCode, str]] = {
    ErrorCode.PAYMENTS_DISABLED: "ntf-purchase.payments-disabled",
    ErrorCode.PLAN_NOT_FOUND: "ntf-purchase.plan-unavailable",
    ErrorCode.SUBSCRIPTION_LIMIT_REACHED: "ntf-purchase.limit-reached",
    ErrorCode.GATEWAY_NOT_AVAILABLE: "ntf-purchase.method-unavailable",
    ErrorCode.GATEWAY_EMAIL_REQUIRED: "ntf-purchase.method-unavailable",
    ErrorCode.PURCHASE_DISCOUNT_USED: "ntf-purchase.retry",
}


def checkout_error_key(error: AppError) -> str:
    return _ERROR_KEYS.get(error.code, "ntf-purchase.failed")


def bot_payment_methods(user: UserDto, methods: list[PaymentMethodDto]) -> list[PaymentMethodDto]:
    # the bot can't ask for an email, so such methods are not offered
    return [m for m in methods if not (m.requires_email and user.email is None)]


def price_in(duration: CatalogDurationDto, currency: Currency) -> Decimal:
    return next(p.price for p in duration.prices if p.currency is currency)


def plans_for(
    purchase_type: PurchaseType, catalog: PlanCatalogDto, current_plan_id: Optional[int]
) -> list[CatalogPlanDto]:
    if purchase_type is PurchaseType.CHANGE:
        return [plan for plan in catalog.plans if plan.id != current_plan_id]
    return catalog.plans


def catalog_query(manager: DialogManager) -> ListActivePlansDto:
    start = manager.start_data if isinstance(manager.start_data, dict) else {}
    code = manager.dialog_data.get(PLAN_CODE_KEY)
    if code is None:
        code = start.get(PLAN_CODE_KEY)
    purchase_type = manager.dialog_data.get("purchase_type", start.get("purchase_type"))
    renew_id = (
        selected_subscription_id(manager) if purchase_type == PurchaseType.RENEW.value else None
    )
    return ListActivePlansDto(plan_code=code, renew_subscription_id=renew_id)


def selected_plan(catalog: PlanCatalogDto, dialog_data: dict[str, Any]) -> Optional[CatalogPlanDto]:
    return next((p for p in catalog.plans if p.id == dialog_data.get("plan_id")), None)


async def start_purchase_steps(
    manager: DialogManager,
    catalog: PlanCatalogDto,
    subscriptions: list[SubscriptionDto],
    methods: Optional[list[PaymentMethodDto]] = None,
) -> Optional[str]:
    """Returns a notification key when the purchase can't start. A retry
    (`methods` given) skips to the order's duration instead of the first step."""
    start = manager.start_data if isinstance(manager.start_data, dict) else {}
    purchase_type = PurchaseType(start.get("purchase_type", PurchaseType.NEW.value))
    manager.dialog_data["purchase_type"] = purchase_type.value
    code = start.get(PLAN_CODE_KEY)
    if code is not None:
        return await _start_by_link(manager, catalog, subscriptions, code)
    target_id = start.get(SELECTED_SUBSCRIPTION_KEY)
    target = next((s for s in subscriptions if s.id == target_id), None)
    if purchase_type is not PurchaseType.NEW and target is None:
        return "ntf-subscription.gone"
    if purchase_type is PurchaseType.RENEW:
        assert target is not None
        if not any(plan.id == target.plan_snapshot.plan_id for plan in catalog.plans):
            return "ntf-purchase.plan-unavailable"
        manager.dialog_data["plan_id"] = target.plan_snapshot.plan_id
        if methods is not None:
            return await select_duration(manager, catalog, start[RETRY_DURATION_KEY], methods)
        await manager.switch_to(Purchase.DURATION)
        return None
    current = target.plan_snapshot.plan_id if target is not None else None
    manager.dialog_data["current_plan_id"] = current
    offered = plans_for(purchase_type, catalog, current)
    if not offered:
        return "ntf-purchase.no-plans"
    if methods is not None:
        if not any(plan.id == start[RETRY_PLAN_KEY] for plan in offered):
            return "ntf-purchase.plan-unavailable"
        manager.dialog_data["plan_id"] = start[RETRY_PLAN_KEY]
        return await select_duration(manager, catalog, start[RETRY_DURATION_KEY], methods)
    await manager.switch_to(Purchase.PLAN)
    return None


async def _start_by_link(
    manager: DialogManager,
    catalog: PlanCatalogDto,
    subscriptions: list[SubscriptionDto],
    code: str,
) -> Optional[str]:
    # a coded catalog holds at most the linked plan
    if not catalog.plans:
        return "ntf-purchase.plan-unavailable"
    plan = catalog.plans[0]
    manager.dialog_data[PLAN_CODE_KEY] = code
    manager.dialog_data["plan_id"] = plan.id
    if any(s.plan_snapshot.plan_id == plan.id for s in subscriptions):
        manager.dialog_data[LINK_CHOICE_KEY] = True
        await manager.switch_to(Purchase.LINK_CHOICE)
    else:
        await manager.switch_to(Purchase.DURATION)
    return None


def _store_method(dialog_data: dict[str, Any], method: dict[str, str]) -> None:
    # a new selection is a new order, not the one already created
    dialog_data.pop(PAYMENT_URL_KEY, None)
    dialog_data["gateway_type"] = method["gateway_type"]
    dialog_data["currency"] = method["currency"]


async def select_duration(
    manager: DialogManager, catalog: PlanCatalogDto, days: int, methods: list[PaymentMethodDto]
) -> Optional[str]:
    """Returns a notification key when the duration can't be bought."""
    plan = selected_plan(catalog, manager.dialog_data)
    duration = next((d for d in plan.durations if d.days == days), None) if plan else None
    if plan is None or duration is None:
        return "ntf-purchase.plan-unavailable"
    if not methods:
        return "ntf-purchase.no-methods"
    data = manager.dialog_data
    data.pop(PAYMENT_URL_KEY, None)
    data["duration_days"] = days
    data["plan_name"] = plan.name
    data["prices"] = {p.currency.value: str(p.price) for p in duration.prices}
    data["methods"] = [
        {"gateway_type": m.gateway_type.value, "currency": m.currency.value} for m in methods
    ]
    # checkout validates the gateway even for a free order, so one is picked silently
    data["method_skipped"] = len(methods) == 1 or price_in(duration, catalog.anchor_currency) == 0
    if data["method_skipped"]:
        _store_method(data, data["methods"][0])
        await manager.switch_to(Purchase.CONFIRM)
    else:
        await manager.switch_to(Purchase.METHOD)
    return None


async def _start_purchase(
    manager: DialogManager, purchase_type: PurchaseType, with_target: bool
) -> None:
    data: dict[str, Any] = {"purchase_type": purchase_type.value}
    if with_target:
        data[SELECTED_SUBSCRIPTION_KEY] = selected_subscription_id(manager)
    # stacked on the caller, so done() goes back to it
    await manager.start(Purchase.PLAN, data=data)


async def on_purchase_new(
    callback: CallbackQuery, widget: Keyboard, dialog_manager: DialogManager
) -> None:
    await _start_purchase(dialog_manager, PurchaseType.NEW, with_target=False)


async def on_purchase_renew(
    callback: CallbackQuery, widget: Keyboard, dialog_manager: DialogManager
) -> None:
    await _start_purchase(dialog_manager, PurchaseType.RENEW, with_target=True)


async def on_purchase_change(
    callback: CallbackQuery, widget: Keyboard, dialog_manager: DialogManager
) -> None:
    await _start_purchase(dialog_manager, PurchaseType.CHANGE, with_target=True)


@inject
async def on_purchase_start(
    start_data: Data,
    manager: DialogManager,
    list_active_plans: FromDishka[ListActivePlansUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    list_payment_methods: FromDishka[ListPaymentMethodsUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = manager.middleware_data[USER_KEY]
    start = start_data if isinstance(start_data, dict) else {}
    retry = start.get(RETRY_PLAN_KEY) is not None
    is_new = start.get("purchase_type", PurchaseType.NEW.value) == PurchaseType.NEW.value
    by_link = start.get(PLAN_CODE_KEY) is not None
    needs_subscriptions = by_link or not is_new
    subscriptions = await list_own_subscriptions(user) if needs_subscriptions else []
    catalog = await list_active_plans(user, catalog_query(manager))
    methods = bot_payment_methods(user, await list_payment_methods(user)) if retry else None
    key = await start_purchase_steps(manager, catalog, subscriptions, methods)
    if key is None:
        return
    text = get_translator(i18n, user).get(key)
    if isinstance(manager.event, CallbackQuery):
        await manager.event.answer(text, show_alert=True)
    elif isinstance(manager.event, Message):
        await manager.event.answer(text)
    if by_link or retry:
        # nothing below to return to
        await manager.start(MainMenu.MAIN, mode=StartMode.RESET_STACK)
    else:
        await manager.done()


async def on_plan_selected(
    callback: CallbackQuery, widget: Button, dialog_manager: DialogManager
) -> None:
    dialog_manager.dialog_data["plan_id"] = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    await dialog_manager.switch_to(Purchase.DURATION)


@inject
async def on_duration_selected(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    list_active_plans: FromDishka[ListActivePlansUseCase],
    list_payment_methods: FromDishka[ListPaymentMethodsUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    key = await select_duration(
        dialog_manager,
        await list_active_plans(user, catalog_query(dialog_manager)),
        int(dialog_manager.item_id),  # type: ignore[attr-defined]
        bot_payment_methods(user, await list_payment_methods(user)),
    )
    if key is not None:
        await callback.answer(get_translator(i18n, user).get(key), show_alert=True)


async def on_duration_back(
    callback: CallbackQuery, widget: Button, dialog_manager: DialogManager
) -> None:
    data = dialog_manager.dialog_data
    if data.get(PLAN_CODE_KEY) is not None:
        if data.get(LINK_CHOICE_KEY):
            await dialog_manager.switch_to(Purchase.LINK_CHOICE)
        else:
            await dialog_manager.start(MainMenu.MAIN, mode=StartMode.RESET_STACK)
    elif data.get("purchase_type") == PurchaseType.RENEW.value:
        await dialog_manager.done()
    else:
        await dialog_manager.switch_to(Purchase.PLAN)


async def on_link_renew(
    callback: CallbackQuery, widget: Button, dialog_manager: DialogManager
) -> None:
    data = dialog_manager.dialog_data
    data["purchase_type"] = PurchaseType.RENEW.value
    data[SELECTED_SUBSCRIPTION_KEY] = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    await dialog_manager.switch_to(Purchase.DURATION)


async def on_link_new(
    callback: CallbackQuery, widget: Button, dialog_manager: DialogManager
) -> None:
    data = dialog_manager.dialog_data
    data["purchase_type"] = PurchaseType.NEW.value
    data.pop(SELECTED_SUBSCRIPTION_KEY, None)
    await dialog_manager.switch_to(Purchase.DURATION)


async def on_method_selected(
    callback: CallbackQuery, widget: Button, dialog_manager: DialogManager
) -> None:
    gateway_type = dialog_manager.item_id  # type: ignore[attr-defined]
    methods = dialog_manager.dialog_data.get("methods", [])
    method = next((m for m in methods if m["gateway_type"] == gateway_type), None)
    if method is None:
        return
    _store_method(dialog_manager.dialog_data, method)
    await dialog_manager.switch_to(Purchase.CONFIRM)


async def on_confirm_back(
    callback: CallbackQuery, widget: Button, dialog_manager: DialogManager
) -> None:
    skipped = dialog_manager.dialog_data.get("method_skipped")
    await dialog_manager.switch_to(Purchase.DURATION if skipped else Purchase.METHOD)


@inject
async def on_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    create_checkout: FromDishka[CreateCheckoutUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    data = dialog_manager.dialog_data
    # a repeated tap on a stale confirm message reuses the order already created
    if data.get(PAYMENT_URL_KEY):
        await dialog_manager.switch_to(Purchase.PAY)
        return
    purchase_type = PurchaseType(data["purchase_type"])
    try:
        result = await create_checkout(
            user,
            CreateCheckoutDto(
                plan_id=data["plan_id"],
                duration_days=data["duration_days"],
                currency=Currency(data["currency"]),
                purchase_type=purchase_type,
                channel=PurchaseChannel.BOT,
                gateway_type=PaymentGatewayType(data["gateway_type"]),
                target_subscription_id=None
                if purchase_type is PurchaseType.NEW
                else selected_subscription_id(dialog_manager),
                plan_code=data.get(PLAN_CODE_KEY),
            ),
        )
    except AppError as error:
        await callback.answer(runner.get(checkout_error_key(error)), show_alert=True)
        return
    if result.confirmation_url is None:
        await callback.answer()
        await dialog_manager.start(MainMenu.MAIN, mode=StartMode.RESET_STACK)
        return
    data[PAYMENT_URL_KEY] = result.confirmation_url
    await dialog_manager.switch_to(Purchase.PAY)

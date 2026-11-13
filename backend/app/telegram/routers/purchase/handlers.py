from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any, Final, Optional, TypeAlias

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Data, DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Keyboard
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub
from pydantic import EmailStr, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from app.core.constants import USER_KEY
from app.core.enums import Currency, PaymentGatewayType, PurchaseChannel, PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.utils.email import normalize_email
from app.modules.settings import GetAccessSettingsUseCase
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
    JoinPaymentWaitlistUseCase,
    ListPaymentMethodsUseCase,
    PaymentMethodDto,
    PriceQuote,
    QuoteCheckoutDto,
    QuoteCheckoutUseCase,
)
from app.modules.users import UserDto
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY, selected_subscription_id
from app.telegram.i18n import get_translator
from app.telegram.notice import answer_notice
from app.telegram.recurring import consent_callback_id
from app.telegram.states import MainMenu, Purchase

PAYMENT_URL_KEY: Final[str] = "payment_url"
# the last order this window created: a new selection's order replaces it
ORDER_ID_KEY: Final[str] = "order_id"
PLAN_CODE_KEY: Final[str] = "plan_code"
RETRY_PLAN_KEY: Final[str] = "retry_plan_id"
RETRY_DURATION_KEY: Final[str] = "retry_duration_days"
# typed in the bot for a gateway that sends a receipt, used for this purchase only
CUSTOMER_EMAIL_KEY: Final[str] = "customer_email"
RECURRING_TERMS_KEY: Final[str] = "recurring_terms"
RECURRING_ACCEPTED_KEY: Final[str] = "recurring_accepted_terms_id"
RECURRING_EVENT_KEY: Final[str] = "recurring_consent_event_id"
_EMAIL_ADAPTER: Final[TypeAdapter[str]] = TypeAdapter(EmailStr)
# the link offered renew-or-new, so its back buttons return there
LINK_CHOICE_KEY: Final[str] = "link_choice"
_ERROR_KEYS: Final[dict[ErrorCode, str]] = {
    ErrorCode.PAYMENTS_DISABLED: "ntf-access.payments-disabled",
    ErrorCode.PLAN_NOT_FOUND: "ntf-purchase.plan-unavailable",
    ErrorCode.SUBSCRIPTION_LIMIT_REACHED: "ntf-purchase.limit-reached",
    ErrorCode.GATEWAY_NOT_AVAILABLE: "ntf-purchase.method-unavailable",
    ErrorCode.GATEWAY_EMAIL_REQUIRED: "ntf-purchase.method-unavailable",
    ErrorCode.PURCHASE_DISCOUNT_USED: "ntf-purchase.discount-used",
    ErrorCode.PRICE_CHANGED: "ntf-recurring.terms-changed",
    ErrorCode.RECURRING_CONSENT_REQUIRED: "ntf-recurring.consent-required",
}


def checkout_error_key(error: AppError) -> str:
    return _ERROR_KEYS.get(error.code, "ntf-purchase.failed")


Quoter: TypeAlias = Callable[[int, Currency], Awaitable[PriceQuote]]


def price_in(duration: CatalogDurationDto, currency: Currency) -> Decimal:
    # the plan's own promotion off; a personal discount shows from the quote on
    price = next(p for p in duration.prices if p.currency is currency)
    return price.price if price.discounted_price is None else price.discounted_price


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


def checkout_quoter(
    user: UserDto, manager: DialogManager, quote_checkout: QuoteCheckoutUseCase
) -> Quoter:
    """What checkout would charge for the selected plan, discounts applied."""

    async def quote(days: int, currency: Currency) -> PriceQuote:
        query = catalog_query(manager)
        return await quote_checkout(
            user,
            QuoteCheckoutDto(
                plan_id=manager.dialog_data["plan_id"],
                duration_days=days,
                currency=currency,
                plan_code=query.plan_code,
                renew_subscription_id=query.renew_subscription_id,
            ),
        )

    return quote


def selected_plan(catalog: PlanCatalogDto, dialog_data: dict[str, Any]) -> Optional[CatalogPlanDto]:
    return next((p for p in catalog.plans if p.id == dialog_data.get("plan_id")), None)


async def start_purchase_steps(
    manager: DialogManager,
    catalog: PlanCatalogDto,
    subscriptions: list[SubscriptionDto],
    methods: Optional[list[PaymentMethodDto]] = None,
    quote: Optional[Quoter] = None,
) -> Optional[str]:
    """Returns a notification key when the purchase can't start. A retry
    (`methods` and `quote` given) skips to the order's duration instead of the first step."""
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
            return "ntf-purchase.renew-plan-unavailable"
        manager.dialog_data["plan_id"] = target.plan_snapshot.plan_id
        if methods is not None and quote is not None:
            return await select_duration(
                manager, catalog, start[RETRY_DURATION_KEY], methods, quote
            )
        await manager.switch_to(Purchase.DURATION)
        return None
    current = target.plan_snapshot.plan_id if target is not None else None
    manager.dialog_data["current_plan_id"] = current
    offered = plans_for(purchase_type, catalog, current)
    if not offered:
        return "ntf-purchase.no-plans"
    if methods is not None and quote is not None:
        if not any(plan.id == start[RETRY_PLAN_KEY] for plan in offered):
            return "ntf-purchase.plan-unavailable"
        manager.dialog_data["plan_id"] = start[RETRY_PLAN_KEY]
        return await select_duration(manager, catalog, start[RETRY_DURATION_KEY], methods, quote)
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


def clear_recurring_choice(data: dict[str, Any]) -> None:
    for key in (RECURRING_TERMS_KEY, RECURRING_ACCEPTED_KEY, RECURRING_EVENT_KEY):
        data.pop(key, None)


def checkout_data(manager: DialogManager) -> CreateCheckoutDto:
    data = manager.dialog_data
    purchase_type = PurchaseType(data["purchase_type"])
    return CreateCheckoutDto(
        plan_id=data["plan_id"],
        duration_days=data["duration_days"],
        currency=Currency(data["currency"]),
        purchase_type=purchase_type,
        channel=PurchaseChannel.BOT,
        gateway_type=PaymentGatewayType(data["gateway_type"]),
        target_subscription_id=None
        if purchase_type is PurchaseType.NEW
        else selected_subscription_id(manager),
        customer_email=data.get(CUSTOMER_EMAIL_KEY),
        plan_code=data.get(PLAN_CODE_KEY),
        replaces_order_id=data.get(ORDER_ID_KEY),
        expected_price=Decimal(data["prices"][data["currency"]]),
        recurring_consent=bool(data.get(RECURRING_ACCEPTED_KEY)),
        recurring_terms_id=data.get(RECURRING_ACCEPTED_KEY),
        consent_event_id=data.get(RECURRING_EVENT_KEY),
    )


async def on_recurring_choice(
    callback: CallbackQuery, widget: Button, dialog_manager: DialogManager
) -> None:
    data = dialog_manager.dialog_data
    if widget.widget_id == "recurring_on" and data.get(RECURRING_TERMS_KEY):
        # A stale message must not authorize terms displayed by a later selection.
        terms_id = data[RECURRING_TERMS_KEY]["terms_id"]
        if dialog_manager.item_id != consent_callback_id(terms_id):  # type: ignore[attr-defined]
            await callback.answer()
            return
        data[RECURRING_ACCEPTED_KEY] = terms_id
        data[RECURRING_EVENT_KEY] = callback.id
    elif widget.widget_id == "recurring_off":
        data.pop(RECURRING_ACCEPTED_KEY, None)
        data.pop(RECURRING_EVENT_KEY, None)
    else:
        return
    data.pop(PAYMENT_URL_KEY, None)
    await callback.answer()


def _store_method(dialog_data: dict[str, Any], method: dict[str, Any]) -> None:
    clear_recurring_choice(dialog_data)
    # a new selection is a new order, not the one already created
    dialog_data.pop(PAYMENT_URL_KEY, None)
    dialog_data["gateway_type"] = method["gateway_type"]
    dialog_data["currency"] = method["currency"]
    dialog_data["requires_email"] = method.get("requires_email", False)
    dialog_data["recurring_available"] = method.get("recurring_available", False)
    dialog_data["recurring_required"] = method.get("recurring_required", False)


async def _after_method(manager: DialogManager) -> None:
    data = manager.dialog_data
    user: UserDto = manager.middleware_data[USER_KEY]
    if data["requires_email"] and user.email is None and not data.get(CUSTOMER_EMAIL_KEY):
        await manager.switch_to(Purchase.EMAIL)
    else:
        await manager.switch_to(Purchase.CONFIRM)


async def select_duration(
    manager: DialogManager,
    catalog: PlanCatalogDto,
    days: int,
    methods: list[PaymentMethodDto],
    quote: Quoter,
) -> Optional[str]:
    """Returns a notification key when the duration can't be bought."""
    plan = selected_plan(catalog, manager.dialog_data)
    duration = next((d for d in plan.durations if d.days == days), None) if plan else None
    if plan is None or duration is None:
        return "ntf-purchase.plan-unavailable"
    if not methods:
        return "ntf-purchase.no-methods"
    try:
        quotes = {
            currency: await quote(days, currency)
            for currency in dict.fromkeys(method.currency for method in methods)
        }
    except AppError:
        return "ntf-purchase.plan-unavailable"
    methods = [
        m
        for m in methods
        if not (
            m.recurring_required
            and quotes[m.currency].final_price > 0
            and (plan.is_trial or days <= 0)
        )
    ]
    if not methods:
        return "ntf-purchase.no-methods"
    data = manager.dialog_data
    data.pop(PAYMENT_URL_KEY, None)
    clear_recurring_choice(data)
    data["duration_days"] = days
    data["plan_name"] = plan.name
    data["plan_icon_id"] = plan.icon_emoji_id
    data["plan_icon_fallback"] = plan.icon_emoji_fallback
    # what checkout charges, and the price before discounts beside it
    data["prices"] = {c.value: str(q.final_price) for c, q in quotes.items()}
    data["base_prices"] = {c.value: str(q.base_price) for c, q in quotes.items()}
    # the same discount whatever the currency
    first = quotes[methods[0].currency]
    data["discount_percent"] = first.discount_percent
    data["discount_source"] = first.discount_source.value
    data["methods"] = [
        {
            "gateway_type": m.gateway_type.value,
            "currency": m.currency.value,
            "requires_email": m.requires_email,
            "recurring_available": m.recurring_available,
            "recurring_required": m.recurring_required,
        }
        for m in methods
    ]
    # checkout validates the gateway even for a free order, so one is picked silently
    data["method_skipped"] = len(methods) == 1 or quotes[methods[0].currency].final_price == 0
    if data["method_skipped"]:
        _store_method(data, data["methods"][0])
        await _after_method(manager)
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
    quote_checkout: FromDishka[QuoteCheckoutUseCase],
    get_access_settings: FromDishka[GetAccessSettingsUseCase],
    join_payment_waitlist: FromDishka[JoinPaymentWaitlistUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = manager.middleware_data[USER_KEY]
    start = start_data if isinstance(start_data, dict) else {}
    retry = start.get(RETRY_PLAN_KEY) is not None
    is_new = start.get("purchase_type", PurchaseType.NEW.value) == PurchaseType.NEW.value
    by_link = start.get(PLAN_CODE_KEY) is not None
    if not (await get_access_settings.system()).payments_enabled:
        await join_payment_waitlist(user)
        text = get_translator(i18n, user).get("ntf-access.payments-disabled")
        await answer_notice(manager.event, text)
        await _leave_purchase(manager, nothing_below=by_link or retry)
        return
    needs_subscriptions = by_link or not is_new
    subscriptions = await list_own_subscriptions(user) if needs_subscriptions else []
    catalog = await list_active_plans(user, catalog_query(manager))
    methods = await list_payment_methods(user) if retry else None
    key = await start_purchase_steps(
        manager, catalog, subscriptions, methods, checkout_quoter(user, manager, quote_checkout)
    )
    if key is None:
        return
    await answer_notice(manager.event, get_translator(i18n, user).get(key))
    await _leave_purchase(manager, nothing_below=by_link or retry)


async def _leave_purchase(manager: DialogManager, *, nothing_below: bool) -> None:
    if nothing_below:
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
    quote_checkout: FromDishka[QuoteCheckoutUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    key = await select_duration(
        dialog_manager,
        await list_active_plans(user, catalog_query(dialog_manager)),
        int(dialog_manager.item_id),  # type: ignore[attr-defined]
        await list_payment_methods(user),
        checkout_quoter(user, dialog_manager, quote_checkout),
    )
    if key is not None:
        await answer_notice(callback, get_translator(i18n, user).get(key))


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
    await _after_method(dialog_manager)


@inject
async def on_email_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorHub],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    try:
        email = _EMAIL_ADAPTER.validate_python(normalize_email(message.text or ""))
    except PydanticValidationError:
        await answer_notice(message, get_translator(i18n, user).get("ntf-purchase.invalid-email"))
        return
    data = dialog_manager.dialog_data
    data.pop(PAYMENT_URL_KEY, None)
    data[CUSTOMER_EMAIL_KEY] = email
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
    join_payment_waitlist: FromDishka[JoinPaymentWaitlistUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    data = dialog_manager.dialog_data
    # a repeated tap on a stale confirm message reuses the order already created
    if data.get(PAYMENT_URL_KEY):
        await dialog_manager.switch_to(Purchase.PAY)
        return
    if (
        data.get("recurring_required")
        and not data.get(RECURRING_ACCEPTED_KEY)
        and Decimal(data["prices"][data["currency"]]) > 0
    ):
        await answer_notice(callback, runner.get("ntf-recurring.consent-required"))
        return
    try:
        result = await create_checkout(user, checkout_data(dialog_manager))
    except AppError as error:
        if error.code is ErrorCode.PAYMENTS_DISABLED:
            # the text promises a message once payments are back
            await join_payment_waitlist(user)
        await answer_notice(callback, runner.get(checkout_error_key(error)))
        if error.code is ErrorCode.RECURRING_CONSENT_REQUIRED:
            data["recurring_available"] = True
            data["recurring_required"] = True
            clear_recurring_choice(data)
        if error.code is ErrorCode.PRICE_CHANGED:
            clear_recurring_choice(data)
            await dialog_manager.switch_to(Purchase.DURATION)
        if error.code is ErrorCode.PURCHASE_DISCOUNT_USED:
            # the shown price had the spent discount in it; picking a duration quotes again
            await dialog_manager.switch_to(Purchase.DURATION)
        return
    if result.confirmation_url is None:
        await callback.answer()
        await dialog_manager.start(MainMenu.MAIN, mode=StartMode.RESET_STACK)
        return
    data[ORDER_ID_KEY] = result.order_id
    data[PAYMENT_URL_KEY] = result.confirmation_url
    await dialog_manager.switch_to(Purchase.PAY)

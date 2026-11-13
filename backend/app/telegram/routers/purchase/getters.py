import html
from decimal import Decimal
from typing import Any, Optional

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub, TranslatorRunner

from app.core.constants import USER_KEY
from app.core.enums import Currency, DiscountSource, PurchaseChannel, PurchaseType
from app.core.exceptions import AppError
from app.modules.legal import ListVisibleLegalDocumentsUseCase
from app.modules.subscriptions import (
    CatalogPlanDto,
    ListActivePlansUseCase,
    ListOwnSubscriptionsUseCase,
    SubscriptionDto,
)
from app.modules.transactions import GetCheckoutRecurringTermsUseCase, QuoteCheckoutUseCase
from app.modules.users import UserDto
from app.telegram.dialogs.context import selected_subscription_id
from app.telegram.dialogs.rendering import TrustedHtml, label_with_icon, render_window_text
from app.telegram.i18n import format_date, format_period, format_price, get_translator
from app.telegram.recurring import consent_callback_id
from app.telegram.routers.purchase.handlers import (
    PAYMENT_URL_KEY,
    PLAN_CODE_KEY,
    RECURRING_ACCEPTED_KEY,
    RECURRING_TERMS_KEY,
    catalog_query,
    checkout_data,
    checkout_quoter,
    clear_recurring_choice,
    plans_for,
    price_in,
    selected_plan,
)


def _price(prices: dict[str, str], currency: str) -> str:
    return format_price(Decimal(prices[currency]))


def _original_price(data: dict[str, Any]) -> str:
    # empty without a discount: the confirm text drops the line
    currency = data["currency"]
    base = data.get("base_prices", {}).get(currency)
    if base is None or Decimal(base) == Decimal(data["prices"][currency]):
        return ""
    return format_price(Decimal(base))


def _runner(dialog_manager: DialogManager, i18n: TranslatorHub) -> TranslatorRunner:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    return get_translator(i18n, user)


def _purchase_type(dialog_manager: DialogManager) -> PurchaseType:
    return PurchaseType(dialog_manager.dialog_data["purchase_type"])


async def _renewed(
    dialog_manager: DialogManager, list_own_subscriptions: ListOwnSubscriptionsUseCase
) -> Optional[SubscriptionDto]:
    if _purchase_type(dialog_manager) is not PurchaseType.RENEW:
        return None
    target_id = selected_subscription_id(dialog_manager)
    owned = await list_own_subscriptions(dialog_manager.middleware_data[USER_KEY])
    return next((s for s in owned if s.id == target_id), None)


def _plan_title(name: str, icon_id: Optional[str], fallback: Optional[str]) -> TrustedHtml:
    """The plan's name behind its icon: the custom emoji, its glyph where it can't render."""
    escaped = html.escape(name)
    if icon_id:
        glyph = html.escape(fallback or "•")
        return TrustedHtml(
            f'<tg-emoji emoji-id="{html.escape(icon_id)}">{glyph}</tg-emoji> {escaped}'
        )
    return TrustedHtml(f"{html.escape(fallback)} {escaped}" if fallback else escaped)


def _catalog_plan_title(plan: CatalogPlanDto) -> TrustedHtml:
    return _plan_title(plan.name, plan.icon_emoji_id, plan.icon_emoji_fallback)


def _plan_details(runner: TranslatorRunner, plan: CatalogPlanDto, period: str = "") -> TrustedHtml:
    return TrustedHtml(
        render_window_text(
            runner,
            "frg-purchase-plan",
            plan_name=_catalog_plan_title(plan),
            # its own blank line after it, gone with it when there is none
            description=f"{plan.description}\n" if plan.description else "",
            traffic_limit=plan.traffic_limit,
            device_limit=plan.device_limit,
            period=period,
        )
    )


def _plan_changed_notice(
    runner: TranslatorRunner, plan: CatalogPlanDto, renewed: Optional[SubscriptionDto]
) -> str:
    # a paid renewal moves the subscription to the plan's terms as sold now
    if renewed is None:
        return ""
    sold = renewed.plan_snapshot
    if (sold.traffic_limit, sold.device_limit, sold.traffic_limit_strategy) == (
        plan.traffic_limit,
        plan.device_limit,
        plan.traffic_limit_strategy,
    ):
        return ""
    return TrustedHtml(render_window_text(runner, "frg-purchase-plan-changed"))


def _discount_notice(runner: TranslatorRunner, percent: int, source: DiscountSource) -> str:
    if percent <= 0 or source is DiscountSource.NONE:
        return ""
    return TrustedHtml(render_window_text(runner, "frg-purchase-discount", percent=percent))


def _type_notice(runner: TranslatorRunner, purchase_type: PurchaseType) -> str:
    if purchase_type is PurchaseType.NEW:
        return ""
    return TrustedHtml(
        render_window_text(runner, "frg-purchase-type-notice", purchase_type=purchase_type.value)
    )


def _duration_back_key(dialog_manager: DialogManager) -> str:
    # a renewal or a plan link has no plan list behind it: back leaves the purchase
    if (
        dialog_manager.dialog_data.get(PLAN_CODE_KEY) is not None
        or _purchase_type(dialog_manager) is PurchaseType.RENEW
    ):
        return "btn-back.general"
    return "btn-purchase.back-plans"


@inject
async def plan_getter(
    dialog_manager: DialogManager,
    list_active_plans: FromDishka[ListActivePlansUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    runner = _runner(dialog_manager, i18n)
    data = dialog_manager.dialog_data
    catalog = await list_active_plans(
        dialog_manager.middleware_data[USER_KEY], catalog_query(dialog_manager)
    )
    plans = plans_for(PurchaseType(data["purchase_type"]), catalog, data.get("current_plan_id"))
    return {
        "window_text": render_window_text(runner, "msg-purchase-plan"),
        "plans": [
            {
                "id": plan.id,
                # a custom emoji goes into the button's icon; a bare glyph has nowhere else to go
                "label": f"{plan.icon_emoji_fallback} {plan.name}"
                if plan.icon_emoji_fallback and not plan.icon_emoji_id
                else plan.name,
                "icon_id": plan.icon_emoji_id,
                "badge": plan.badge.value if plan.badge is not None else "",
            }
            for plan in plans
        ],
        "back_text": label_with_icon(runner, "btn-back.general"),
    }


@inject
async def duration_getter(
    dialog_manager: DialogManager,
    list_active_plans: FromDishka[ListActivePlansUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    quote_checkout: FromDishka[QuoteCheckoutUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    runner = _runner(dialog_manager, i18n)
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    catalog = await list_active_plans(user, catalog_query(dialog_manager))
    plan = selected_plan(catalog, dialog_manager.dialog_data)
    back_text = label_with_icon(runner, _duration_back_key(dialog_manager))
    if plan is None:
        # dropped from the catalog while the window stayed open
        return {
            "window_text": render_window_text(runner, "msg-window-gone"),
            "durations": [],
            "back_text": back_text,
        }
    renewed = await _renewed(dialog_manager, list_own_subscriptions)
    quote = checkout_quoter(user, dialog_manager, quote_checkout)
    currency = catalog.anchor_currency
    durations = []
    discount_notice = ""
    for duration in plan.durations:
        # the price checkout would charge, personal discounts included
        try:
            quoted = await quote(duration.days, currency)
            price = quoted.final_price
            discount_notice = discount_notice or _discount_notice(
                runner, quoted.discount_percent, quoted.discount_source
            )
        except AppError:
            price = price_in(duration, currency)
        durations.append(
            {
                "days": duration.days,
                "label": runner.get(
                    "btn-purchase.duration",
                    period=format_period(runner, duration.days),
                    price=format_price(price),
                    currency_symbol=currency.symbol,
                ),
            }
        )
    return {
        "window_text": render_window_text(
            runner,
            "msg-purchase-duration",
            plan_details=_plan_details(runner, plan),
            discount_notice=discount_notice,
            plan_changed_notice=_plan_changed_notice(runner, plan, renewed),
        ),
        "durations": durations,
        "back_text": back_text,
    }


@inject
async def method_getter(
    dialog_manager: DialogManager,
    list_active_plans: FromDishka[ListActivePlansUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    runner = _runner(dialog_manager, i18n)
    data = dialog_manager.dialog_data
    catalog = await list_active_plans(
        dialog_manager.middleware_data[USER_KEY], catalog_query(dialog_manager)
    )
    plan = selected_plan(catalog, data)
    return {
        "window_text": render_window_text(
            runner,
            "msg-purchase-method",
            plan_details=_plan_details(runner, plan, format_period(runner, data["duration_days"]))
            if plan is not None
            else "",
            discount_notice=_discount_notice(
                runner,
                data.get("discount_percent", 0),
                DiscountSource(data.get("discount_source", DiscountSource.NONE.value)),
            ),
        ),
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
        "back_text": label_with_icon(runner, "btn-purchase.back-duration"),
    }


@inject
async def email_getter(
    dialog_manager: DialogManager, i18n: FromDishka[TranslatorHub], **kwargs: Any
) -> dict[str, Any]:
    runner = _runner(dialog_manager, i18n)
    return {
        "window_text": render_window_text(runner, "msg-purchase-email"),
        "back_text": label_with_icon(runner, "btn-back.general"),
    }


@inject
async def confirm_getter(
    dialog_manager: DialogManager,
    list_active_plans: FromDishka[ListActivePlansUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    list_visible_legal_documents: FromDishka[ListVisibleLegalDocumentsUseCase],
    get_recurring_terms: FromDishka[GetCheckoutRecurringTermsUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    runner = _runner(dialog_manager, i18n)
    data = dialog_manager.dialog_data
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    documents = await list_visible_legal_documents.execute(PurchaseChannel.BOT, user.language)
    terms_notice = (
        TrustedHtml(render_window_text(runner, "frg-purchase-terms-notice")) if documents else ""
    )
    catalog = await list_active_plans(user, catalog_query(dialog_manager))
    plan = selected_plan(catalog, data)
    renewed = await _renewed(dialog_manager, list_own_subscriptions)
    purchase_type = _purchase_type(dialog_manager)
    # an empty value drops its line, as for a plan gone from the catalog
    traffic_limit: object = plan.traffic_limit if plan is not None else ""
    device_limit: object = plan.device_limit if plan is not None else ""
    terms = None
    if data.get("recurring_available") and plan is not None:
        try:
            terms = await get_recurring_terms(user, checkout_data(dialog_manager))
        except AppError:
            terms = None
    previous = data.get(RECURRING_TERMS_KEY, {})
    if terms is None or previous.get("terms_id") != terms.terms_id:
        clear_recurring_choice(data)
    if terms is not None:
        data[RECURRING_TERMS_KEY] = terms.model_dump(mode="json")
        data["prices"][data["currency"]] = str(terms.initial_amount)
        data.setdefault("base_prices", {})[data["currency"]] = str(terms.amount_limit)
    accepted = bool(terms and data.get(RECURRING_ACCEPTED_KEY) == terms.terms_id)
    recurring_notice = html.escape(terms.summary) if terms else ""
    return {
        "window_text": render_window_text(
            runner,
            "msg-purchase-confirm",
            purchase_type=purchase_type.value,
            plan_name=_plan_title(
                data["plan_name"], data.get("plan_icon_id"), data.get("plan_icon_fallback")
            ),
            traffic_limit=traffic_limit,
            device_limit=device_limit,
            period=format_period(runner, data["duration_days"]),
            price=_price(data["prices"], data["currency"]),
            original_price=_original_price(data),
            currency_symbol=Currency(data["currency"]).symbol,
            method=runner.get(f"gateway-name.{data['gateway_type']}"),
            type_notice=_type_notice(runner, purchase_type),
            plan_changed_notice=_plan_changed_notice(runner, plan, renewed) if plan else "",
            terms_notice=terms_notice,
        )
        + (f"\n\n{recurring_notice}" if recurring_notice else ""),
        "recurring_choices": [{"id": consent_callback_id(terms.terms_id)}] if terms else [],
        "recurring_on": terms is not None and not accepted,
        "recurring_off": accepted,
        "recurring_terms": accepted,
        "recurring_on_text": runner.get("btn-recurring.consent-off"),
        "recurring_off_text": runner.get("btn-recurring.consent-on"),
        "recurring_terms_text": runner.get("btn-recurring.terms"),
        "pay_text": label_with_icon(runner, "btn-purchase.pay"),
        "back_text": label_with_icon(
            runner,
            "btn-purchase.back-duration"
            if data.get("method_skipped")
            else "btn-purchase.back-method",
        ),
    }


@inject
async def recurring_terms_getter(
    dialog_manager: DialogManager, i18n: FromDishka[TranslatorHub], **kwargs: Any
) -> dict[str, Any]:
    data = dialog_manager.dialog_data
    terms = data.get(RECURRING_TERMS_KEY, {})
    accepted = terms.get("terms_id") == data.get(RECURRING_ACCEPTED_KEY)
    runner = _runner(dialog_manager, i18n)
    return {
        "window_text": html.escape(terms["text"])
        if accepted and terms
        else runner.get("ntf-recurring.unavailable"),
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


@inject
async def link_choice_getter(
    dialog_manager: DialogManager,
    list_active_plans: FromDishka[ListActivePlansUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    runner = _runner(dialog_manager, i18n)
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    catalog = await list_active_plans(user, catalog_query(dialog_manager))
    plan = selected_plan(catalog, dialog_manager.dialog_data)
    owned = [
        s
        for s in await list_own_subscriptions(user)
        if plan is not None and s.plan_snapshot.plan_id == plan.id
    ]
    return {
        "window_text": render_window_text(
            runner, "msg-purchase-link-choice", plan_name=_catalog_plan_title(plan)
        )
        if plan is not None
        else render_window_text(runner, "msg-window-gone"),
        "subscriptions": [
            {
                "id": s.id,
                "label": label_with_icon(
                    runner,
                    "btn-purchase.link-renew",
                    subscription=f"{s.plan_snapshot.name} — {format_date(s.expire_at)}",
                ),
            }
            for s in owned
        ],
        "new_text": label_with_icon(runner, "btn-purchase.link-new") if plan is not None else "",
        "has_plan": plan is not None,
        "menu_text": label_with_icon(runner, "btn-purchase.menu"),
    }

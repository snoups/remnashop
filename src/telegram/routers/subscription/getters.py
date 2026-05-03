import re
from typing import Any, cast

from adaptix import Retort
from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import TranslatorRunner
from src.application.common.dao import PaymentGatewayDao, PlanDao, SettingsDao, SubscriptionDao
from src.application.dto import PlanDto, PriceDetailsDto, UserDto
from src.application.services import PricingService
from src.application.use_cases.plan.queries.match import MatchPlan, MatchPlanDto
from src.application.use_cases.user.queries.plans import GetAvailableTrial
from src.application.use_cases.user.queries.plans import GetAvailablePlans
from src.core.config import AppConfig
from src.core.enums import PurchaseType
from src.core.utils.i18n_helpers import (
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.core.utils.time import get_traffic_reset_delta
from src.telegram.states import Subscription

from .payment_options import build_payment_method_options, find_payment_method_option


CUSTOM_EMOJI_PATTERN = re.compile(
    r'<tg-emoji\s+emoji-id=["\'](?P<id>\d+)["\'][^>]*>.*?</tg-emoji>',
    re.DOTALL,
)


def format_plan_button_label(name: str) -> tuple[str, str | None]:
    match = CUSTOM_EMOJI_PATTERN.search(name)
    icon_custom_emoji_id = match.group("id") if match else None
    label = CUSTOM_EMOJI_PATTERN.sub("", name)
    label = " ".join(label.split())
    return label or name, icon_custom_emoji_id


@inject
async def subscription_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    subscription_dao: FromDishka[SubscriptionDao],
    get_available_trial: FromDishka[GetAvailableTrial],
    **kwargs: Any,
) -> dict[str, Any]:
    current_subscription = await subscription_dao.get_current(user.telegram_id)
    available_trial = await get_available_trial.system(user) if user.is_trial_available else None
    has_active = bool(current_subscription and not current_subscription.is_trial)
    is_unlimited = current_subscription.is_unlimited if current_subscription else False
    data: dict[str, Any] = {
        "has_subscription": False,
        "has_active_subscription": has_active,
        "is_not_unlimited": not is_unlimited,
        "trial_available": user.is_trial_available and bool(available_trial),
        "is_trial": False,
        "status": None,
        "traffic_limit": None,
        "device_limit": None,
        "expire_time": None,
        "traffic_strategy": None,
        "reset_time": None,
    }

    if not current_subscription:
        return data

    data.update(
        {
            "has_subscription": True,
            "is_trial": current_subscription.is_trial,
            "status": current_subscription.current_status,
            "traffic_limit": i18n_format_traffic_limit(current_subscription.traffic_limit),
            "device_limit": i18n_format_device_limit(current_subscription.device_limit),
            "expire_time": i18n_format_expire_time(current_subscription.expire_at),
            "connection_url": config.bot.mini_app_url or current_subscription.url,
            "traffic_strategy": current_subscription.traffic_limit_strategy,
            "reset_time": i18n_format_expire_time(
                get_traffic_reset_delta(
                    current_subscription.traffic_limit_strategy,
                    current_subscription.created_at,
                )
            ),
        }
    )
    return data


@inject
async def plan_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    plan_dao: FromDishka[PlanDao],
    subscription_dao: FromDishka[SubscriptionDao],
    match_plan: FromDishka[MatchPlan],
    **kwargs: Any,
) -> dict[str, Any]:
    plan_id: int = dialog_manager.start_data["plan_id"]  # type: ignore[call-overload, index, assignment]
    plan = await plan_dao.get_by_id(plan_id)

    if not plan:
        raise ValueError(f"Plan with id '{plan_id}' not found")

    current_subscription = await subscription_dao.get_current(user.telegram_id)

    if current_subscription:
        matched_plan = await match_plan.system(
            MatchPlanDto(plan_snapshot=current_subscription.plan_snapshot, plans=[plan])
        )

        if matched_plan and not current_subscription.is_unlimited:
            purchase_type = PurchaseType.RENEW
        else:
            purchase_type = PurchaseType.CHANGE
    else:
        purchase_type = PurchaseType.NEW

    dialog_manager.dialog_data["only_single_plan"] = True
    dialog_manager.dialog_data["purchase_type"] = purchase_type

    return {
        "plan_id": [plan.id],
        "name": i18n.get(plan.name),
        "description": i18n.get(plan.description) if plan.description else False,
        "purchase_type": purchase_type,
    }


@inject
async def plans_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    get_available_plans: FromDishka[GetAvailablePlans],
    **kwargs: Any,
) -> dict[str, Any]:
    plans = await get_available_plans.system(user)

    formatted_plans = []
    for plan in plans:
        name = i18n.get(plan.name)
        label, icon_custom_emoji_id = format_plan_button_label(name)
        formatted_plans.append(
            {
                "id": plan.id,
                "name": label,
                "icon_custom_emoji_id": icon_custom_emoji_id,
            }
        )

    return {
        "plans": formatted_plans,
    }


@inject
async def duration_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    retort: FromDishka[Retort],
    i18n: FromDishka[TranslatorRunner],
    settings_dao: FromDishka[SettingsDao],
    pricing_service: FromDishka[PricingService],
    **kwargs: Any,
) -> dict[str, Any]:
    raw_plan = dialog_manager.dialog_data.get(PlanDto.__name__)

    if not raw_plan:
        logger.debug("PlanDto not found in dialog data")
        await dialog_manager.start(state=Subscription.MAIN)
        return {}

    plan = retort.load(raw_plan, PlanDto)
    settings = await settings_dao.get()
    currency = settings.default_currency
    only_single_plan = dialog_manager.dialog_data.get("only_single_plan", False)
    dialog_manager.dialog_data["is_free"] = False
    durations = []

    for duration in plan.durations:
        key, kw = i18n_format_days(duration.days)
        price = pricing_service.calculate(user, duration.get_price(currency), currency)
        durations.append(
            {
                "days": duration.days,
                "period": i18n.get(key, **kw),
                "final_amount": price.final_amount,
                "discount_percent": price.discount_percent,
                "original_amount": price.original_amount,
                "currency": currency.symbol,
            }
        )

    return {
        "plan": i18n.get(plan.name),
        "description": i18n.get(plan.description) if plan.description else False,
        "type": plan.type,
        "devices": i18n_format_device_limit(plan.device_limit),
        "traffic": i18n_format_traffic_limit(plan.traffic_limit),
        "durations": durations,
        "period": 0,
        "final_amount": 0,
        "currency": "",
        "only_single_plan": only_single_plan,
        "discount_percent": pricing_service.get_effective_discount(user),
        "is_personal_discount": pricing_service.is_largest_discount_personal(user),
    }


@inject
async def payment_method_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    retort: FromDishka[Retort],
    i18n: FromDishka[TranslatorRunner],
    payment_gateway_dao: FromDishka[PaymentGatewayDao],
    pricing_service: FromDishka[PricingService],
    **kwargs: Any,
) -> dict[str, Any]:
    raw_plan = dialog_manager.dialog_data.get(PlanDto.__name__)

    if not raw_plan:
        logger.error("PlanDto not found in dialog data")
        await dialog_manager.start(state=Subscription.MAIN)
        return {}

    plan = retort.load(raw_plan, PlanDto)
    gateways = await payment_gateway_dao.get_active()
    selected_duration = dialog_manager.dialog_data["selected_duration"]
    only_single_duration = dialog_manager.dialog_data.get("only_single_duration", False)
    duration = plan.get_duration(selected_duration)

    if not duration:
        raise ValueError(f"Duration '{selected_duration}' not found in plan '{plan.name}'")

    payment_methods = []
    gateways_by_type = {gateway.type: gateway for gateway in gateways}
    for option in build_payment_method_options(gateways):
        gateway = gateways_by_type[option.gateway_type]
        raw_price = duration.get_price(gateway.currency)
        price = pricing_service.calculate(user, raw_price, gateway.currency)
        payment_methods.append(
            {
                "id": option.id,
                "payment_label": option.label
                or i18n.get("gateway-type", gateway_type=option.gateway_type),
                "final_amount": price.final_amount,
                "original_amount": price.original_amount,
                "discount_percent": price.discount_percent,
                "currency": gateway.currency.symbol,
            }
        )

    key, kw = i18n_format_days(duration.days)

    return {
        "plan": i18n.get(plan.name),
        "description": i18n.get(plan.description) if plan.description else False,
        "type": plan.type,
        "devices": i18n_format_device_limit(plan.device_limit),
        "traffic": i18n_format_traffic_limit(plan.traffic_limit),
        "period": i18n.get(key, **kw),
        "payment_methods": payment_methods,
        "final_amount": 0,
        "currency": "",
        "only_single_duration": only_single_duration,
        "discount_percent": pricing_service.get_effective_discount(user),
        "is_personal_discount": pricing_service.is_largest_discount_personal(user),
    }


@inject
async def confirm_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    retort: FromDishka[Retort],
    i18n: FromDishka[TranslatorRunner],
    payment_gateway_dao: FromDishka[PaymentGatewayDao],
    pricing_service: FromDishka[PricingService],
    **kwargs: Any,
) -> dict[str, Any]:
    raw_plan = dialog_manager.dialog_data.get(PlanDto.__name__)

    if not raw_plan:
        logger.debug("PlanDto not found in dialog data")
        await dialog_manager.start(state=Subscription.MAIN)
        return {}

    plan = retort.load(raw_plan, PlanDto)
    selected_duration = dialog_manager.dialog_data["selected_duration"]
    only_single_duration = dialog_manager.dialog_data.get("only_single_duration", False)
    is_free = dialog_manager.dialog_data.get("is_free", False)
    selected_payment_method = dialog_manager.dialog_data["selected_payment_method"]
    purchase_type = dialog_manager.dialog_data["purchase_type"]
    gateways = await payment_gateway_dao.get_active()
    selected_option = find_payment_method_option(gateways, selected_payment_method)
    payment_gateway = await payment_gateway_dao.get_by_type(selected_option.gateway_type)
    duration = plan.get_duration(selected_duration)

    if not duration:
        raise ValueError(f"Duration '{selected_duration}' not found in plan '{plan.name}'")

    if not payment_gateway:
        raise ValueError(f"Not found PaymentGateway by selected type '{selected_payment_method}'")

    result_url = dialog_manager.dialog_data["payment_url"]
    pricing_data = dialog_manager.dialog_data["final_pricing"]
    pricing = retort.load(pricing_data, PriceDetailsDto)

    key, kw = i18n_format_days(duration.days)
    payment_options = build_payment_method_options(gateways)

    return {
        "purchase_type": purchase_type,
        "plan": i18n.get(plan.name),
        "description": i18n.get(plan.description) if plan.description else False,
        "type": plan.type,
        "devices": i18n_format_device_limit(plan.device_limit),
        "traffic": i18n_format_traffic_limit(plan.traffic_limit),
        "period": i18n.get(key, **kw),
        "payment_method": selected_option.gateway_type,
        "payment_method_label": selected_option.label
        or i18n.get("gateway-type", gateway_type=selected_option.gateway_type),
        "final_amount": pricing.final_amount,
        "discount_percent": pricing.discount_percent,
        "original_amount": pricing.original_amount,
        "is_personal_discount": pricing_service.is_largest_discount_personal(user),
        "currency": payment_gateway.currency.symbol,
        "url": result_url,
        "only_single_gateway": len(payment_options) == 1,
        "only_single_duration": only_single_duration,
        "is_free": is_free,
    }


@inject
async def getter_connect(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    subscription_dao: FromDishka[SubscriptionDao],
    **kwargs: Any,
) -> dict[str, Any]:
    current_subscription = await subscription_dao.get_current(user.telegram_id)

    if not current_subscription:
        raise ValueError(f"User '{user.telegram_id}' has no active subscription after purchase")

    return {
        "is_mini_app": config.bot.is_mini_app,
        "connection_url": config.bot.mini_app_url or current_subscription.url,
        "connectable": True,
    }


@inject
async def success_payment_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    subscription_dao: FromDishka[SubscriptionDao],
    **kwargs: Any,
) -> dict[str, Any]:
    start_data = cast(dict[str, Any], dialog_manager.start_data)
    purchase_type: PurchaseType = start_data["purchase_type"]
    subscription = await subscription_dao.get_current(user.telegram_id)

    if not subscription:
        raise ValueError(f"User '{user.telegram_id}' has no active subscription after purchase")

    return {
        "purchase_type": purchase_type,
        "plan_name": subscription.plan_snapshot.name,
        "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
        "device_limit": i18n_format_device_limit(subscription.device_limit),
        "expire_time": i18n_format_expire_time(subscription.expire_at),
        "added_duration": i18n_format_days(subscription.plan_snapshot.duration),
        "is_mini_app": config.bot.is_mini_app,
        "connection_url": config.bot.mini_app_url or subscription.url,
        "connectable": True,
    }

from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.constants import USER_KEY
from src.core.utils.adapter import DialogDataAdapter
from src.core.utils.formatters import i18n_format_days_to_duration
from src.infrastructure.database.models.dto import PlanDto, PlanSnapshotDto, UserDto
from src.services.payment_gateway import PaymentGatewayService
from src.services.plan import PlanService


@inject
async def subscription_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {}


@inject
async def plans_getter(
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plans: list[PlanDto] = await plan_service.get_available_plans(user)

    formatted_plans = [
        {
            "id": plan.id,
            "name": plan.name,
        }
        for plan in plans
    ]

    return {
        "plans": formatted_plans,
    }


@inject
async def duration_getter(
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        return {}

    currency = await payment_gateway_service.get_default_currency()
    durations = []

    for duration in plan.durations:
        key, kw = i18n_format_days_to_duration(duration.days)
        durations.append(
            {
                "days": duration.days,
                "period": i18n.get(key, **kw),
                "price": duration.get_price(currency),
                "currency": currency.symbol,
            }
        )

    return {
        "plan": plan.name,
        "type": plan.type,
        "devices": plan.device_limit,
        "traffic": plan.traffic_limit,
        "period": 0,
        "durations": durations,
        "price": 0,
        "currency": "",
    }


@inject
async def payment_method_getter(
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        return {}

    gateways = await payment_gateway_service.filter_active()
    selected_duration = dialog_manager.dialog_data["selected_duration"]
    duration = plan.get_duration(selected_duration)

    if not duration:
        return {}

    payment_methods = []
    for gateway in gateways:
        payment_methods.append(
            {
                "gateway_type": gateway.type,
                "price": duration.get_price(gateway.currency),
                "currency": gateway.currency.symbol,
            }
        )

    key, kw = i18n_format_days_to_duration(duration.days)

    return {
        "plan": plan.name,
        "type": plan.type,
        "devices": plan.device_limit,
        "traffic": plan.traffic_limit,
        "period": i18n.get(key, **kw),
        "payment_methods": payment_methods,
        "price": 0,
        "currency": "",
    }


@inject
async def confirm_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        return {}

    selected_duration = dialog_manager.dialog_data["selected_duration"]
    selected_payment_method = dialog_manager.dialog_data["selected_payment_method"]
    payment_gateway = await payment_gateway_service.get_by_type(selected_payment_method)
    duration = plan.get_duration(selected_duration)

    if not duration or not payment_gateway:
        return {}

    transaction_plan = PlanSnapshotDto(
        id=plan.id,
        name=plan.name,
        type=plan.type,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        duration=duration.days,
        squad_ids=plan.squad_ids,
    )

    price = duration.get_price(payment_gateway.currency)

    url = await payment_gateway_service.create_payment(
        user=user,
        plan=transaction_plan,
        price=price,
        gateway_type=selected_payment_method,
    )

    key, kw = i18n_format_days_to_duration(duration.days)

    return {
        "plan": plan.name,
        "type": plan.type,
        "devices": plan.device_limit,
        "traffic": plan.traffic_limit,
        "period": i18n.get(key, **kw),
        "payment_method": selected_payment_method,
        "price": price,
        "currency": payment_gateway.currency.symbol,
        "url": url,
    }

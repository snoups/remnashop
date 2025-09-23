from typing import Any, Optional

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger
from remnawave import RemnawaveSDK
from remnawave.models import GetAllInternalSquadsResponseDto

from src.core.enums import Currency, PlanAvailability, PlanType
from src.core.utils.adapter import DialogDataAdapter
from src.infrastructure.database.models.dto import PlanDto, PlanDurationDto, PlanPriceDto
from src.services.plan import PlanService


@inject
async def plans_getter(
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    plans: list[PlanDto] = await plan_service.get_all()
    formatted_plans = [
        {
            "id": plan.id,
            "name": plan.name,
            "is_active": plan.is_active,
        }
        for plan in plans
    ]

    return {
        "plans": formatted_plans,
    }


def generate_prices(price: float) -> list[PlanPriceDto]:
    return [PlanPriceDto(currency=currency, price=price) for currency in Currency]


async def plan_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if plan is None:
        plan = PlanDto(
            durations=[
                PlanDurationDto(days=7, prices=generate_prices(100)),
                PlanDurationDto(days=30, prices=generate_prices(100)),
            ],
        )
        adapter.save(plan)

    helpers = {
        "is_unlimited_traffic": plan.is_unlimited_traffic,
        "is_unlimited_devices": plan.is_unlimited_devices,
    }

    data = plan.model_dump()
    data.update(helpers)
    return data


async def type_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {"types": list(PlanType)}


async def availability_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {"availability": list(PlanAvailability)}


async def durations_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        return {}

    durations = [duration.model_dump() for duration in plan.durations]
    return {"durations": durations}


def get_prices_for_duration(
    durations: list[PlanDurationDto],
    target_days: int,
) -> Optional[list[PlanPriceDto]]:
    for duration in durations:
        if duration.days == target_days:
            return duration.prices
    return []


async def prices_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        return {}

    duration_selected = dialog_manager.dialog_data["duration_selected"]
    prices = get_prices_for_duration(plan.durations, duration_selected)
    prices_data = [price.model_dump() for price in prices] if prices else []

    return {
        "duration": duration_selected,
        "prices": prices_data,
    }


async def price_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    duration_selected = dialog_manager.dialog_data.get("duration_selected")
    currency_selected = dialog_manager.dialog_data.get("currency_selected")
    logger.info(currency_selected)
    return {
        "duration": duration_selected,
        "currency": currency_selected,
    }


async def allowed_users_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        return {}

    return {"allowed_users": plan.allowed_user_ids if plan.allowed_user_ids else []}


@inject
async def squads_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        return {}

    response = await remnawave.internal_squads.get_internal_squads()

    if not isinstance(response, GetAllInternalSquadsResponseDto):
        return {}

    existing_squad_uuids = {squad.uuid for squad in response.internal_squads}

    if plan.squad_ids:
        plan_squad_uuids_set = set(plan.squad_ids)
        valid_squad_uuids_set = plan_squad_uuids_set.intersection(existing_squad_uuids)
        plan.squad_ids = list(valid_squad_uuids_set)

    adapter.save(plan)

    squads = [
        {
            "uuid": squad.uuid,
            "name": squad.name,
            "selected": True if squad.uuid in plan.squad_ids else False,
        }
        for squad in response.internal_squads
    ]

    return {
        "squads": squads,
    }

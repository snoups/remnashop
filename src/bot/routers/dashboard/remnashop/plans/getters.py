from decimal import Decimal
from typing import Any, Optional

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from remnapy import RemnawaveSDK
from remnapy.enums.users import TrafficLimitStrategy

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


async def configurator_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if plan is None:
        plan = PlanDto(
            durations=[
                PlanDurationDto(
                    days=7,
                    prices=[
                        PlanPriceDto(currency=Currency.USD, price=Decimal(0.5)),
                        PlanPriceDto(currency=Currency.XTR, price=Decimal(30)),
                        PlanPriceDto(currency=Currency.RUB, price=Decimal(50)),
                    ],
                ),
                PlanDurationDto(
                    days=30,
                    prices=[
                        PlanPriceDto(currency=Currency.USD, price=Decimal(1)),
                        PlanPriceDto(currency=Currency.XTR, price=Decimal(60)),
                        PlanPriceDto(currency=Currency.RUB, price=Decimal(100)),
                    ],
                ),
                PlanDurationDto(
                    days=365,
                    prices=[
                        PlanPriceDto(currency=Currency.USD, price=Decimal(10)),
                        PlanPriceDto(currency=Currency.XTR, price=Decimal(600)),
                        PlanPriceDto(currency=Currency.RUB, price=Decimal(1000)),
                    ],
                ),
                PlanDurationDto(
                    days=-1,
                    prices=[
                        PlanPriceDto(currency=Currency.USD, price=Decimal(100)),
                        PlanPriceDto(currency=Currency.XTR, price=Decimal(6000)),
                        PlanPriceDto(currency=Currency.RUB, price=Decimal(10000)),
                    ],
                ),
            ],
        )
        adapter.save(plan)

    helpers = {
        "is_edit": dialog_manager.dialog_data.get("is_edit", False),
        "is_unlimited_traffic": plan.is_unlimited_traffic,
        "is_unlimited_devices": plan.is_unlimited_devices,
        "plan_type": plan.type,
        "availability_type": plan.availability,
    }

    data = plan.model_dump()
    data.update(helpers)
    return data


async def name_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    return {"name": plan.name or False}


async def description_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    return {"description": plan.description or False}


async def tag_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    return {"tag": plan.tag or False}


async def type_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {"types": list(PlanType)}


async def availability_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {"availability": list(PlanAvailability)}


async def traffic_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    strategys = [
        {
            "strategy": strategy,
            "selected": strategy.name == plan.traffic_limit_strategy,
        }
        for strategy in TrafficLimitStrategy
    ]

    return {"strategys": strategys}


async def durations_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    durations = [duration.model_dump() for duration in plan.durations]

    return {
        "deletable": len(durations) > 1,
        "durations": durations,
    }


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
        raise ValueError("PlanDto not found in dialog data")

    selected_duration = dialog_manager.dialog_data["selected_duration"]
    prices = get_prices_for_duration(plan.durations, selected_duration)
    prices_data = [price.model_dump() for price in prices] if prices else []

    return {
        "duration": selected_duration,
        "prices": prices_data,
    }


async def price_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    selected_duration = dialog_manager.dialog_data.get("selected_duration")
    selected_currency = dialog_manager.dialog_data.get("selected_currency")
    return {
        "duration": selected_duration,
        "currency": selected_currency,
    }


async def allowed_users_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

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
        raise ValueError("PlanDto not found in dialog data")

    internal_response = await remnawave.internal_squads.get_internal_squads()
    internal_dict = {s.uuid: s.name for s in internal_response.internal_squads}
    internal_squads_names = ", ".join(
        internal_dict.get(squad, str(squad)) for squad in plan.internal_squads
    )

    external_response = await remnawave.external_squads.get_external_squads()
    external_dict = {s.uuid: s.name for s in external_response.external_squads}
    external_squad_name = external_dict.get(plan.external_squad) if plan.external_squad else False

    return {
        "internal_squads": internal_squads_names or False,
        "external_squad": external_squad_name or False,
    }


@inject
async def internal_squads_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    result = await remnawave.internal_squads.get_internal_squads()
    existing_squad_uuids = {squad.uuid for squad in result.internal_squads}

    if plan.internal_squads:
        plan_squad_uuids_set = set(plan.internal_squads)
        valid_squad_uuids_set = plan_squad_uuids_set.intersection(existing_squad_uuids)
        plan.internal_squads = list(valid_squad_uuids_set)

    adapter.save(plan)

    squads = [
        {
            "uuid": squad.uuid,
            "name": squad.name,
            "selected": True if squad.uuid in plan.internal_squads else False,
        }
        for squad in result.internal_squads
    ]

    return {
        "squads": squads,
    }


@inject
async def external_squads_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    result = await remnawave.external_squads.get_external_squads()
    existing_squad_uuids = {squad.uuid for squad in result.external_squads}

    if plan.external_squad and plan.external_squad not in existing_squad_uuids:
        plan.external_squad = None

    adapter.save(plan)

    squads = [
        {
            "uuid": squad.uuid,
            "name": squad.name,
            "selected": True if squad.uuid == plan.external_squad else False,
        }
        for squad in result.external_squads
    ]

    return {
        "squads": squads,
    }

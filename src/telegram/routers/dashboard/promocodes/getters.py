from typing import Any, Optional

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common import TranslatorRunner
from src.application.common.dao import PlanDao, PromocodeDao
from src.core.enums import PromoAudience


@inject
async def list_getter(
    dialog_manager: DialogManager,
    promocode_dao: FromDishka[PromocodeDao],
    **kwargs: Any,
) -> dict[str, Any]:
    promocodes = await promocode_dao.get_all()

    items = [
        {
            "id": p.id,
            "code": p.code,
            "discount_percent": p.discount_percent,
            "is_active": p.is_active,
        }
        for p in promocodes
    ]

    return {
        "promocodes": items,
        "has_promocodes": bool(items),
    }


@inject
async def plans_getter(
    dialog_manager: DialogManager,
    plan_dao: FromDishka[PlanDao],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    all_plans = await plan_dao.get_all()
    active_plans = [p for p in all_plans if p.is_active]

    items = [
        {
            "id": plan.id,
            "name": i18n.get(plan.name),
        }
        for plan in active_plans
    ]

    dialog_manager.dialog_data["_plans_cache"] = items

    return {
        "plans": items,
        "has_plans": bool(items),
    }


async def audience_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {"audiences": list(PromoAudience)}


@inject
async def configurator_getter(
    dialog_manager: DialogManager,
    promocode_dao: FromDishka[PromocodeDao],
    **kwargs: Any,
) -> dict[str, Any]:
    data = dialog_manager.dialog_data
    is_edit: bool = data.get("is_edit", False)

    activations_count: Optional[int] = None
    if is_edit:
        promo_id = data.get("promocode_id")
        if promo_id is not None:
            activations_count = await promocode_dao.count_activations(int(promo_id))

    return {
        "is_edit": is_edit,
        "code": data.get("code", "—"),
        "discount_percent": data.get("discount_percent", "—"),
        "plan_name": data.get("plan_name", "—"),
        "audience": data.get("audience", ""),
        "max_activations": data.get("max_activations", "—"),
        "expires_at_str": data.get("expires_at_str", "—"),
        "is_active": data.get("is_active", True),
        "activations_count": activations_count if activations_count is not None else 0,
        "promocode_id": data.get("promocode_id"),
    }

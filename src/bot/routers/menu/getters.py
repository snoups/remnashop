from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from remnawave import RemnawaveSDK

from src.infrastructure.database.models.dto import UserDto
from src.services.plan import PlanService


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    remnawave: FromDishka[RemnawaveSDK],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    # remna_user = await remnawave.users.get_user_by_username(user.remnaname)
    # plan = await plan_service.get(plan_id=int(remna_user.tag.split("_")[-1]))

    # logger.critical(remna_user)
    # logger.critical(plan)

    subscription = None  # user.current_subscription

    return {
        "id": str(user.telegram_id),
        "name": user.name,
        "status": subscription.status if subscription else None,
        "type": subscription.plan_type if subscription else None,
        "traffic_limit": subscription.traffic_limit if subscription else None,
        "devices_limit": subscription.device_limit if subscription else None,
        "expiry_time": subscription.expiry_time if subscription else None,
        "is_privileged": user.is_privileged,
    }

from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.core.utils.formatters import (
    i18n_format_expire_time,
    i18n_format_limit,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import UserDto
from src.services.plan import PlanService
from src.services.subscription import SubscriptionService


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    plan_service: FromDishka[PlanService],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    plan = await plan_service.get_trial_plan()
    has_any_subscription = await subscription_service.has_any_subscription(user)

    if not user.current_subscription:
        return {
            "id": str(user.telegram_id),
            "name": user.name,
            "status": None,
            "is_privileged": user.is_privileged,
            "trial": not has_any_subscription and plan,
        }

    expiry_time = (
        i18n_format_limit(user.current_subscription.plan.duration)
        if user.current_subscription.plan.is_unlimited_duration
        else i18n_format_expire_time(user.current_subscription.expiry_time)
        if user.current_subscription.expiry_time
        else "N/A"
    )

    return {
        "id": str(user.telegram_id),
        "name": user.name,
        "status": user.current_subscription.status,
        "type": user.current_subscription.plan.type,
        "traffic_limit": i18n_format_traffic_limit(user.current_subscription.plan.traffic_limit),
        "device_limit": i18n_format_limit(user.current_subscription.plan.device_limit),
        "expiry_time": expiry_time,
        "is_privileged": user.is_privileged,
    }

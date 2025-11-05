from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.config import AppConfig
from src.core.utils.formatters import (
    format_username_to_url,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import UserDto
from src.services.plan import PlanService
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    plan_service: FromDishka[PlanService],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    plan = await plan_service.get_trial_plan()
    has_used_trial = await subscription_service.has_used_trial(user)
    support_username = config.bot.support_username.get_secret_value()
    support_link = format_username_to_url(support_username, i18n.get("contact-support"))

    base_data = {
        "user_id": str(user.telegram_id),
        "user_name": user.name,
        "personal_discount": user.personal_discount,
        "support": support_link,
        "has_subscription": user.has_subscription,
        "miniapp_url": config.bot.mini_app_url.get_secret_value(),
    }

    subscription = user.current_subscription

    if not subscription:
        base_data.update(
            {
                "status": None,
                "is_trial": False,
                "trial_available": not has_used_trial and plan,
                "has_device_limit": False,
                "connetable": False,
            }
        )
        return base_data

    base_data.update(
        {
            "status": subscription.status,
            "type": subscription.get_subscription_type,
            "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
            "device_limit": i18n_format_device_limit(subscription.device_limit),
            "expire_time": i18n_format_expire_time(subscription.expire_at),
            "is_trial": subscription.is_trial,
            "has_device_limit": subscription.has_devices_limit if subscription.is_active else False,
            "connetable": subscription.is_active,
            "subscription_url": subscription.url,
        }
    )

    return base_data


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    subscription = user.current_subscription

    if not subscription:
        raise ValueError(f"Current subscription for user '{user.telegram_id}' not found")

    devices = await remnawave_service.get_devices_user(user)

    formatted_devices = [
        {
            "hwid": device.hwid,
            "platform": device.platform,
            "device_model": device.device_model,
            "user_agent": device.user_agent,
        }
        for device in devices
    ]

    return {
        "current_count": len(devices),
        "max_count": i18n_format_device_limit(subscription.device_limit),
        "devices": formatted_devices,
        "devices_empty": len(devices) == 0,
    }

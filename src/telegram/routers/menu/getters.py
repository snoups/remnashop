from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Remnawave, TranslatorRunner
from src.application.common.dao import ReferralDao, SettingsDao, SubscriptionDao
from src.application.dto import UserDto
from src.application.services import BotService
from src.application.use_cases.misc.queries.menu import GetMenuData
from src.core.config import AppConfig
from src.core.exceptions import MenuRenderError
from src.core.utils.i18n_helpers import (
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.core.utils.time import get_traffic_reset_delta


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    bot_service: FromDishka[BotService],
    i18n: FromDishka[TranslatorRunner],
    get_menu_data: FromDishka[GetMenuData],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        menu_data = await get_menu_data(user)
        support_url = bot_service.get_support_url(text=i18n.get("message.help"))

        data: dict[str, Any] = {
            # user
            "telegram_id": user.telegram_id,
            "name": user.name,
            "personal_discount": user.personal_discount,
            # ui / config
            "is_mini_app": config.bot.is_mini_app,
            "support_url": support_url,
            # referral
            "referral_enabled": menu_data.is_referral_enabled,
            # defaults
            "has_subscription": False,
            "connectable": False,
            "trial_available": False,
            "has_device_limit": False,
            "is_trial": False,
            # subscription-related (nullable)
            "status": None,
            "subscription_type": None,
            "traffic_limit": None,
            "device_limit": None,
            "expire_time": None,
            "reset_time": None,
            "connection_url": None,
            "row_1_buttons": [b for b in menu_data.custom_buttons if b.index in (1, 2)],
            "row_2_buttons": [b for b in menu_data.custom_buttons if b.index in (3, 4)],
            "row_3_buttons": [b for b in menu_data.custom_buttons if b.index in (5, 6)],
        }

        if not menu_data.current_subscription:
            logger.debug(f"User {user.telegram_id} has no active subscription")
            data["trial_available"] = menu_data.is_trial_available and menu_data.available_trial
            return data

        subscription = menu_data.current_subscription

        data.update(
            {
                "has_subscription": True,
                "is_trial": subscription.is_trial,
                "traffic_strategy": subscription.traffic_limit_strategy,
                "status": subscription.current_status,
                "subscription_type": subscription.limit_type,
                "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
                "device_limit": i18n_format_device_limit(subscription.device_limit),
                "expire_time": i18n_format_expire_time(subscription.expire_at),
                "reset_time": i18n_format_expire_time(
                    get_traffic_reset_delta(subscription.traffic_limit_strategy)
                ),
                "connectable": subscription.is_active,
                "has_device_limit": (
                    subscription.has_devices_limit or subscription.device_limit == 0
                )
                if subscription.is_active
                else False,
                "connection_url": config.bot.mini_app_url
                if isinstance(config.bot.mini_app_url, str)
                else subscription.url,
            }
        )
        logger.debug(f"Menu data for user {user.telegram_id}: {data}")
        return data

    except Exception as e:
        raise MenuRenderError(str(e)) from e


def get_platform_icon(platform: str | None) -> str:
    platform_icons = {
        "ios": "🍎",
        "android": "🤖",
        "windows": "🖥️",
        "macos": "💻",
        "linux": "🐧",
    }

    default_icon = "📱"

    if not platform:
        return default_icon
    return platform_icons.get(platform.lower(), default_icon)


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    subscription_dao: FromDishka[SubscriptionDao],
    remnawave: FromDishka[Remnawave],
    **kwargs: Any,
) -> dict[str, Any]:
    current_subscription = await subscription_dao.get_current(user.telegram_id)

    if not current_subscription:
        raise ValueError(f"Current subscription for user '{user.telegram_id}' not found")

    devices = await remnawave.get_devices(current_subscription.user_remna_id)

    formatted_devices = [
        {
            "short_hwid": device.hwid[:32],
            "hwid": device.hwid,
            "platform": device.platform,
            "device_model": device.device_model,
            "user_agent": device.user_agent,
            "label": f"{get_platform_icon(device.platform)} "
            f"{device.platform} ({device.device_model})",
        }
        for device in devices
    ]

    dialog_manager.dialog_data["hwid_map"] = formatted_devices

    return {
        "current_count": len(devices),
        "max_count": i18n_format_device_limit(current_subscription.device_limit),
        "devices": formatted_devices,
        "devices_empty": len(devices) == 0,
        "has_devices": len(devices) > 0,
    }


@inject
async def device_confirm_delete_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    **kwargs: Any,
) -> dict[str, Any]:
    selected_label = dialog_manager.dialog_data.get("selected_device_label", "")
    return {"selected_device_label": selected_label}


@inject
async def invite_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    bot_service: FromDishka[BotService],
    i18n: FromDishka[TranslatorRunner],
    settings_dao: FromDishka[SettingsDao],
    referral_dao: FromDishka[ReferralDao],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_dao.get()
    referrals = await referral_dao.get_referrals_count(user.telegram_id)
    payments = await referral_dao.get_referrals_with_payment_count(user.telegram_id)
    referral_url = await bot_service.get_referral_url(user.referral_code)
    support_url = bot_service.get_support_url(text=i18n.get("message.withdraw-points"))

    return {
        "reward_type": settings.referral.reward.type,
        "referrals": referrals,
        "payments": payments,
        "points": user.points,
        "is_points_reward": settings.referral.reward.is_points,
        "has_points": True if user.points > 0 else False,
        "referral_url": referral_url,
        "withdraw": support_url,
    }


@inject
async def invite_about_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    settings_dao: FromDishka[SettingsDao],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_dao.get()
    reward_config = settings.referral.reward.config

    max_level = settings.referral.level.value
    identical_reward = settings.referral.reward.is_identical

    reward_levels: dict[str, str] = {}
    for lvl, val in reward_config.items():
        if lvl.value <= max_level:
            reward_levels[f"reward_level_{lvl.value}"] = i18n.get(
                "msg-invite-reward",
                value=val,
                reward_strategy_type=settings.referral.reward.strategy,
                reward_type=settings.referral.reward.type,
            )

    return {
        **reward_levels,
        "reward_type": settings.referral.reward.type,
        "reward_strategy_type": settings.referral.reward.strategy,
        "accrual_strategy": settings.referral.accrual_strategy,
        "identical_reward": identical_reward,
        "max_level": max_level,
    }

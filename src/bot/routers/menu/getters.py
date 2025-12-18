from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.config import AppConfig
from src.core.exceptions import MenuRenderingError
from src.core.utils.formatters import (
    format_username_to_url,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import UserDto
from src.services.plan import PlanService
from src.services.referral import ReferralService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    plan_service: FromDishka[PlanService],
    subscription_service: FromDishka[SubscriptionService],
    settings_service: FromDishka[SettingsService],
    referral_service: FromDishka[ReferralService],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        plan = await plan_service.get_trial_plan()
        has_used_trial = await subscription_service.has_used_trial(user.telegram_id)
        support_username = config.bot.support_username.get_secret_value()
        ref_link = await referral_service.get_ref_link(user.referral_code)
        support_link = format_username_to_url(support_username, i18n.get("contact-support-help"))

        base_data = {
            "user_id": str(user.telegram_id),
            "user_name": user.name,
            "personal_discount": user.personal_discount,
            "support": support_link,
            "invite": i18n.get("referral-invite-message", url=ref_link),
            "has_subscription": user.has_subscription,
            "is_app": config.bot.is_mini_app,
            "is_referral_enable": await settings_service.is_referral_enable(),
        }

        subscription = user.current_subscription

        if not subscription:
            base_data.update(
                {
                    "status": None,
                    "is_trial": False,
                    "trial_available": not has_used_trial and plan,
                    "has_device_limit": False,
                    "connectable": False,
                }
            )
            return base_data

        base_data.update(
            {
                "status": subscription.get_status,
                "type": subscription.get_subscription_type,
                "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
                "device_limit": i18n_format_device_limit(subscription.device_limit),
                "expire_time": i18n_format_expire_time(subscription.expire_at),
                "is_trial": subscription.is_trial,
                "traffic_strategy": subscription.traffic_limit_strategy,
                "reset_time": subscription.get_expire_time,
                "has_device_limit": subscription.has_devices_limit
                if subscription.is_active
                else False,
                "connectable": subscription.is_active,
                "url": config.bot.mini_app_url or subscription.url,
            }
        )

        return base_data
    except Exception as exception:
        raise MenuRenderingError(str(exception)) from exception


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    if not user.current_subscription:
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
        "max_count": i18n_format_device_limit(user.current_subscription.device_limit),
        "devices": formatted_devices,
        "devices_empty": len(devices) == 0,
    }


@inject
async def invite_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    config: AppConfig,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    referral_service: FromDishka[ReferralService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get_referral_settings()
    referrals = await referral_service.get_referral_count(user.telegram_id)
    payments = await referral_service.get_reward_count(user.telegram_id)
    ref_link = await referral_service.get_ref_link(user.referral_code)
    support_username = config.bot.support_username.get_secret_value()
    support_link = format_username_to_url(
        support_username, i18n.get("contact-support-withdraw-points")
    )

    return {
        "reward_type": settings.reward.type,
        "referrals": referrals,
        "payments": payments,
        "points": user.points,
        "is_points_reward": settings.reward.is_points,
        "has_points": True if user.points > 0 else False,
        "referral_link": ref_link,
        "invite": i18n.get("referral-invite-message", url=ref_link),
        "withdraw": support_link,
    }


@inject
async def invite_about_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get_referral_settings()
    reward_config = settings.reward.config

    max_level = settings.level.value
    identical_reward = settings.reward.is_identical

    reward_levels: dict[str, str] = {}
    for lvl, val in reward_config.items():
        if lvl.value <= max_level:
            reward_levels[f"reward_level_{lvl.value}"] = i18n.get(
                "msg-invite-reward",
                value=val,
                reward_strategy_type=settings.reward.strategy,
                reward_type=settings.reward.type,
            )

    return {
        **reward_levels,
        "reward_type": settings.reward.type,
        "reward_strategy_type": settings.reward.strategy,
        "accrual_strategy": settings.accrual_strategy,
        "identical_reward": identical_reward,
        "max_level": max_level,
    }

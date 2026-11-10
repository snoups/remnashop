from typing import Any, Optional

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub, TranslatorRunner
from remnapy.enums import TrafficLimitStrategy

from app.core.config import AppConfig
from app.core.constants import USER_KEY
from app.core.enums import PurchaseChannel, SubscriptionStatus
from app.modules.banners import GetBannerForDisplayUseCase
from app.modules.legal import ListVisibleLegalDocumentsUseCase
from app.modules.referrals import GetReferralSettingsUseCase
from app.modules.settings import GetShopSettingsUseCase
from app.modules.subscriptions import (
    GetAvailableTrialUseCase,
    ListOwnActiveSubscriptionsUseCase,
    ListOwnSubscriptionsUseCase,
    SubscriptionDto,
)
from app.modules.translations import strip_serializer_escapes
from app.modules.users import UserDto
from app.telegram.banners import get_banner_media
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.context import build_condition_data, menu_flags
from app.telegram.dialogs.rendering import (
    TrustedHtml,
    banner_within_caption,
    render_dialog_buttons,
    render_window_text,
    resolve_variable_kwargs,
)
from app.telegram.i18n import format_datetime, get_translator


def menu_subscription(
    active: Optional[SubscriptionDto], owned: list[SubscriptionDto]
) -> Optional[SubscriptionDto]:
    """The subscription the menu describes: the active one, else the latest
    expired, so the customer sees it ran out rather than that they never had one."""
    if active is not None:
        return active
    expired = [s for s in owned if s.status == SubscriptionStatus.EXPIRED]
    return max(expired, key=lambda s: s.expire_at, default=None)


def subscription_menu_values(
    runner: TranslatorRunner,
    subscription: Optional[SubscriptionDto],
    *,
    extra_count: int,
    trial_available: bool,
) -> dict[str, Any]:
    """menu.main's subscription_* text variables. They need the translator,
    which catalog resolvers don't get, so they are rendered here."""
    values: dict[str, Any] = {
        "subscription_status": "",
        "subscription_traffic_limit": "",
        "subscription_device_limit": "",
        "subscription_expire_at": "",
    }
    if subscription is not None:
        # limits go in as strings, so Fluent doesn't group the digits
        traffic = subscription.effective_traffic_limit
        devices = subscription.effective_device_limit
        unlimited = strip_serializer_escapes(runner.get("frg-subscription-unlimited"))
        values = {
            "subscription_status": strip_serializer_escapes(
                runner.get("frg-subscription-status", status=subscription.status.value)
            ),
            "subscription_traffic_limit": (
                strip_serializer_escapes(
                    runner.get("frg-subscription-traffic-limit", traffic_limit=str(traffic))
                )
                if traffic
                else unlimited
            ),
            "subscription_device_limit": str(devices) if devices else unlimited,
            "subscription_expire_at": format_datetime(subscription.expire_at),
        }
    if subscription is None:
        block = render_window_text(
            runner, "frg-menu-no-subscription", trial_available=int(trial_available)
        )
        return {**values, "subscription_block": TrustedHtml(block)}
    # no helper for the traffic reset date yet, so the RESET texts name none
    resets = subscription.traffic_limit_strategy != TrafficLimitStrategy.NO_RESET
    block = render_window_text(
        runner,
        "frg-menu-subscription",
        status=subscription.status.value,
        is_trial=int(subscription.is_trial),
        traffic_strategy="RESET" if resets else "NO_RESET",
        trial_available=int(trial_available),
        traffic_limit=values["subscription_traffic_limit"],
        device_limit=values["subscription_device_limit"],
        expire_at=values["subscription_expire_at"],
        extra_count=str(extra_count) if extra_count > 0 else "",
    )
    return {**values, "subscription_block": TrustedHtml(block)}


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    get_banner: FromDishka[GetBannerForDisplayUseCase],
    list_own_active_subscriptions: FromDishka[ListOwnActiveSubscriptionsUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    get_available_trial: FromDishka[GetAvailableTrialUseCase],
    get_shop_settings: FromDishka[GetShopSettingsUseCase],
    get_referral_settings: FromDishka[GetReferralSettingsUseCase],
    list_visible_legal_documents: FromDishka[ListVisibleLegalDocumentsUseCase],
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    window = await dialog_config_cache.get_window("menu.main")
    # no banner name: the admin turned the banner off for this window, no fallback
    banner = (
        await get_banner_media(get_banner, config, user, window.banner_name)
        if window.banner_name
        else None
    )

    active = await list_own_active_subscriptions(user)
    # an expired subscription still opens from "My subscriptions" to be renewed, and holds its slot
    owned = await list_own_subscriptions(user)
    can_purchase, referral_enabled, single_subscription = await menu_flags(
        owned, get_shop_settings, get_referral_settings
    )
    data: dict[str, Any] = await build_condition_data(
        user,
        active,
        get_available_trial,
        cabinet_url=config.cabinet.url,
        can_purchase=can_purchase,
        referral_enabled=referral_enabled,
        single_subscription=single_subscription,
    )
    data["subscriptions_count"] = len(owned)
    data["legal_available"] = bool(
        await list_visible_legal_documents.execute(PurchaseChannel.BOT, user.language)
    )
    subscription_values = subscription_menu_values(
        runner,
        menu_subscription(data["subscription"], owned),
        extra_count=len(active) - 1,
        trial_available=data["trial_available"],
    )
    data["menu_text"] = render_window_text(
        runner, "msg-main-menu", **subscription_values, **resolve_variable_kwargs(data)
    )
    data["banner"] = banner_within_caption(banner, data["menu_text"])
    data["buttons"] = await render_dialog_buttons("menu.main", dialog_config_cache, runner, data)
    return data

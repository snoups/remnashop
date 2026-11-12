from decimal import Decimal
from typing import Any, Union

from aiogram import Bot
from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub, TranslatorRunner

from app.core.config import AppConfig
from app.core.constants import USER_KEY
from app.modules.banners import GetBannerForDisplayUseCase
from app.modules.referrals import (
    GetOwnReferralStatsUseCase,
    GetReferralSettingsUseCase,
    ListBonusDaysTargetsUseCase,
    ReferralSettingsDto,
)
from app.modules.settings import GetShopSettingsUseCase
from app.modules.subscriptions import (
    GetAvailableTrialUseCase,
    ListOwnActiveSubscriptionsUseCase,
    ListOwnSubscriptionsUseCase,
)
from app.modules.translations import strip_serializer_escapes
from app.modules.users import UserDto
from app.telegram.banners import get_banner_media
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.context import build_condition_data, menu_flags
from app.telegram.dialogs.rendering import (
    label_with_icon,
    render_dialog_buttons,
    render_window_text,
    resolve_variable_kwargs,
)
from app.telegram.i18n import format_date, get_translator
from app.telegram.middlewares._codes import REFERRAL_PREFIX


def referral_url(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start={REFERRAL_PREFIX}{code}"


@inject
async def referrals_getter(
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    get_banner: FromDishka[GetBannerForDisplayUseCase],
    list_own_active_subscriptions: FromDishka[ListOwnActiveSubscriptionsUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    get_available_trial: FromDishka[GetAvailableTrialUseCase],
    get_shop_settings: FromDishka[GetShopSettingsUseCase],
    get_referral_settings: FromDishka[GetReferralSettingsUseCase],
    get_own_referral_stats: FromDishka[GetOwnReferralStatsUseCase],
    bot: Bot,
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    active = await list_own_active_subscriptions(user)
    # the purchase cap counts an expired subscription too, as checkout does
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
        owned_count=len(owned),
    )
    window = await dialog_config_cache.get_window("referrals.main")
    data["banner"] = (
        await get_banner_media(get_banner, config, user, window.banner_name)
        if window.banner_name
        else None
    )

    stats = await get_own_referral_stats(user)
    me = await bot.me()
    data["has_points"] = stats.points > 0
    data["has_bonus_days"] = stats.bonus_days > 0
    shop = await get_shop_settings.system()
    data["referral_reset_enabled"] = shop.referral_reset_enabled
    data["support_url"] = (
        f"https://t.me/{shop.support_telegram}" if shop.support_telegram else shop.support_url or ""
    )
    data["referral_url"] = (
        referral_url(me.username, stats.referral_code)
        if stats.referral_code and me.username
        else ""
    )
    data["copy_text"] = label_with_icon(runner, "btn-referrals.copy")
    # referral_url reaches the text through resolve_variable_kwargs
    data["window_text"] = render_window_text(
        runner,
        "msg-referrals",
        # a zero line is dropped; level 1 always shows
        referrals_level_1=stats.counts_by_level.get(1, 0),
        referrals_level_2=stats.counts_by_level.get(2) or "",
        points=str(stats.points) if stats.points else "",
        bonus_days=stats.bonus_days or "",
        **resolve_variable_kwargs(data),
    )
    data["buttons"] = await render_dialog_buttons(
        "referrals.main", dialog_config_cache, runner, data
    )
    return data


@inject
async def redeem_target_getter(
    dialog_manager: DialogManager,
    list_bonus_days_targets: FromDishka[ListBonusDaysTargetsUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    return {
        "subscriptions": [
            {"id": s.id, "label": f"{s.plan_snapshot.name} — {format_date(s.expire_at)}"}
            for s in await list_bonus_days_targets(user)
        ],
        "window_text": render_window_text(
            runner, "msg-referrals-redeem-target", bonus_days=user.bonus_days
        ),
        "back_text": label_with_icon(runner, "btn-back.general"),
    }


def _amount(value: Decimal) -> Union[int, Decimal]:
    # an int selects its plural form; a fraction is shown as typed, without trailing zeros
    return int(value) if value == value.to_integral_value() else value.normalize()


def reward_about_values(runner: TranslatorRunner, settings: ReferralSettingsDto) -> dict[str, Any]:
    def terms(level: int) -> str:
        return strip_serializer_escapes(
            runner.get(
                "frg-referral-terms",
                reward_strategy=settings.reward_strategy.value,
                reward_type=settings.reward_type.value,
                amount=_amount(settings.reward_amounts.get(level, Decimal(0))),
            )
        )

    deeper = [
        strip_serializer_escapes(runner.get("frg-referral-level", level=level, terms=terms(level)))
        for level in range(2, settings.max_level + 1)
        if settings.reward_amounts.get(level, Decimal(0)) > 0
    ]
    levels = (
        "\n".join([strip_serializer_escapes(runner.get("frg-referral-levels")), *deeper])
        if deeper
        else ""
    )
    return {
        "invitee_reward_amount": settings.invitee_reward_amount,
        "invitee_reward_type": settings.invitee_reward_type.value,
        "reward_terms": terms(1),
        "accrual_strategy": settings.accrual_strategy.value,
        "reward_levels": levels,
        "reward_type": settings.reward_type.value,
    }


@inject
async def referrals_about_getter(
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    get_banner: FromDishka[GetBannerForDisplayUseCase],
    get_referral_settings: FromDishka[GetReferralSettingsUseCase],
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    window = await dialog_config_cache.get_window("referrals.about")
    data: dict[str, Any] = {
        "banner": (
            await get_banner_media(get_banner, config, user, window.banner_name)
            if window.banner_name
            else None
        )
    }
    values = reward_about_values(runner, await get_referral_settings.system())
    data["window_text"] = render_window_text(runner, "msg-referrals-about", **values)
    data["buttons"] = await render_dialog_buttons(
        "referrals.about", dialog_config_cache, runner, data
    )
    return data

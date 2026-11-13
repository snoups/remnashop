import html
from typing import Any, Awaitable, Callable, Final, Optional, TypeAlias

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.core.constants import USER_KEY
from app.core.enums import SubscriptionStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.banners import GetBannerForDisplayUseCase
from app.modules.referrals import GetReferralSettingsUseCase
from app.modules.settings import GetShopSettingsUseCase
from app.modules.subscriptions import (
    DeviceDto,
    GetAvailableTrialUseCase,
    ListDevicesUseCase,
    ListOwnSubscriptionsUseCase,
    SubscriptionDto,
    SubscriptionRefDto,
)
from app.modules.transactions import GetOwnRecurringPaymentUseCase
from app.modules.users import UserDto
from app.telegram.banners import window_banner
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.context import build_condition_data, menu_flags, selected_subscription_id
from app.telegram.dialogs.rendering import (
    UNAVAILABLE_BUTTONS_KEY,
    label_with_icon,
    render_dialog_buttons,
    render_window_text,
    resolve_variable_kwargs,
)
from app.telegram.i18n import format_date, get_translator
from app.telegram.recurring import consent_callback_id
from app.telegram.routers.subscriptions.handlers import SINGLE_RESET_KEY

_KNOWN_PLATFORMS: Final[frozenset[str]] = frozenset({"ios", "android", "windows", "macos", "linux"})


def _platform_icon_key(platform: Optional[str]) -> str:
    normalized = (platform or "default").lower()
    return normalized if normalized in _KNOWN_PLATFORMS else "default"


@inject
async def subscriptions_list_getter(
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    get_banner: FromDishka[GetBannerForDisplayUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    get_available_trial: FromDishka[GetAvailableTrialUseCase],
    get_shop_settings: FromDishka[GetShopSettingsUseCase],
    get_referral_settings: FromDishka[GetReferralSettingsUseCase],
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    subscriptions = await list_own_subscriptions(user)
    active = [s for s in subscriptions if s.status is not SubscriptionStatus.EXPIRED]
    can_purchase, referral_enabled, single_subscription = await menu_flags(
        subscriptions, get_shop_settings, get_referral_settings
    )
    data: dict[str, Any] = await build_condition_data(
        user,
        active,
        get_available_trial,
        cabinet_url=config.cabinet.url,
        can_purchase=can_purchase,
        referral_enabled=referral_enabled,
        single_subscription=single_subscription,
        owned_count=len(subscriptions),
    )
    data["banner"] = await window_banner(
        "subscriptions.list", dialog_config_cache, get_banner, config, user
    )
    data["subscriptions"] = [
        {
            "id": s.id,
            "label": runner.get(
                "btn-subscriptions.item",
                status=s.status.value,
                plan_name=s.plan_snapshot.name,
                expire_at=format_date(s.expire_at),
            ),
        }
        for s in subscriptions
    ]
    data["window_text"] = render_window_text(
        runner, "msg-subscriptions-list", **resolve_variable_kwargs(data)
    )
    data["buttons"] = await render_dialog_buttons(
        "subscriptions.list", dialog_config_cache, runner, data
    )
    return data


@inject
async def subscription_card_getter(
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    get_banner: FromDishka[GetBannerForDisplayUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    get_available_trial: FromDishka[GetAvailableTrialUseCase],
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    get_own_recurring_payment: FromDishka[GetOwnRecurringPaymentUseCase],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    data: dict[str, Any] = await build_condition_data(
        user,
        await list_own_subscriptions(user),
        get_available_trial,
        cabinet_url=config.cabinet.url,
        selected_id=selected_subscription_id(dialog_manager),
    )
    data["banner"] = await window_banner(
        "subscriptions.card", dialog_config_cache, get_banner, config, user
    )
    subscription: Optional[SubscriptionDto] = data["subscription"]
    data["auto_renew_on"] = False
    data["auto_renew_off"] = False
    data["auto_renew_terms"] = False
    data["auto_renew_choices"] = []
    dialog_manager.dialog_data.pop("auto_renew_terms_id", None)
    if subscription is None:
        # expired or deleted while the card stayed open
        data["window_text"] = render_window_text(runner, "msg-window-gone")
    else:
        recurring = await get_own_recurring_payment(user, subscription.id)
        data["auto_renew_on"] = recurring.available and not recurring.enabled
        data["auto_renew_off"] = recurring.enabled
        data["auto_renew_terms"] = bool(recurring.enabled and recurring.accepted_terms)
        data["auto_renew_terms_text"] = runner.get("btn-recurring.terms")
        if recurring.terms is not None:
            dialog_manager.dialog_data["auto_renew_terms_id"] = recurring.terms.terms_id
            data["auto_renew_choices"] = [{"id": consent_callback_id(recurring.terms.terms_id)}]
        data["auto_renew_text"] = runner.get(
            "btn-recurring.disable" if recurring.enabled else "btn-recurring.enable"
        )
        data["window_text"] = render_window_text(
            runner,
            "msg-subscription-card",
            plan_name=subscription.plan_snapshot.name,
            status=subscription.status.value,
            is_trial=int(subscription.is_trial),
            expire_at=format_date(subscription.expire_at),
            traffic_limit=subscription.effective_traffic_limit,
            device_limit=subscription.effective_device_limit,
            **resolve_variable_kwargs(data),
        )
        if recurring.enabled or recurring.available:
            state_key = "frg-subscription-recurring-off"
            if recurring.enabled:
                state_key = (
                    "frg-subscription-recurring"
                    if recurring.available
                    else "frg-subscription-recurring-paused"
                )
            data["window_text"] += "\n\n" + runner.get(
                state_key,
                amount=str(recurring.amount_limit),
                currency=recurring.currency,
                days=recurring.duration_days,
            )
        if not recurring.enabled and recurring.terms is not None:
            data["window_text"] += "\n\n" + html.escape(recurring.terms.summary)
    data["buttons"] = await render_dialog_buttons(
        "subscriptions.card", dialog_config_cache, runner, data
    )
    return data


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    list_devices: FromDishka[ListDevicesUseCase],
    get_shop_settings: FromDishka[GetShopSettingsUseCase],
    i18n: FromDishka[TranslatorHub],
    dialog_config_cache: FromDishka[DialogConfigCache],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    shop = await get_shop_settings.system()
    # a tap on a device opens nothing while single resets are off
    dialog_manager.dialog_data[SINGLE_RESET_KEY] = shop.device_single_reset_enabled
    unavailable: set[str] = set()
    if not shop.device_all_reset_enabled:
        unavailable |= {"menu.device_confirm_delete_all", "delete_all_devices"}
    if not shop.link_reset_enabled:
        unavailable |= {"menu.device_confirm_reissue", "reissue_subscription"}

    subscription_id = selected_subscription_id(dialog_manager)
    subscription = next(
        (s for s in await list_own_subscriptions(user) if s.id == subscription_id), None
    )
    devices: list[DeviceDto] = []
    if subscription is not None:
        try:
            devices = await list_devices(user, SubscriptionRefDto(subscription_id=subscription.id))
        except (NotFoundError, ValidationError):
            subscription = None

    formatted: list[dict[str, Any]] = [
        {
            "index": index,
            "hwid": device.hwid,
            "label": runner.get(
                "btn-devices.item",
                platform_icon=runner.get(f"platform-icon.{_platform_icon_key(device.platform)}"),
                platform=device.platform or "?",
                device_model=device.device_model or "?",
                created_at=format_date(device.created_at),
            ),
        }
        for index, device in enumerate(devices)
    ]
    dialog_manager.dialog_data["hwid_map"] = formatted

    data: dict[str, Any] = {
        "devices": formatted,
        "has_devices": len(formatted) > 0,
        "window_text": (
            render_window_text(
                runner,
                "msg-menu-devices",
                devices_current=len(formatted),
                devices_max=subscription.effective_device_limit,
                **resolve_variable_kwargs({}),
            )
            if subscription is not None
            # expired or deleted while the window stayed open; the action
            # handlers send the customer back to the subscriptions
            else render_window_text(runner, "msg-window-gone")
        ),
        UNAVAILABLE_BUTTONS_KEY: unavailable,
    }
    data["buttons"] = await render_dialog_buttons("menu.devices", dialog_config_cache, runner, data)
    return data


_Getter: TypeAlias = Callable[..., Awaitable[dict[str, Any]]]


def _confirm_getter(text_key: str, window_key: str) -> _Getter:
    @inject
    async def getter(
        dialog_manager: DialogManager,
        i18n: FromDishka[TranslatorHub],
        dialog_config_cache: FromDishka[DialogConfigCache],
        **kwargs: Any,
    ) -> dict[str, Any]:
        user: UserDto = dialog_manager.middleware_data[USER_KEY]
        runner = get_translator(i18n, user)
        data: dict[str, Any] = {
            "window_text": render_window_text(runner, text_key, **resolve_variable_kwargs({}))
        }
        data["buttons"] = await render_dialog_buttons(window_key, dialog_config_cache, runner, data)
        return data

    return getter


device_confirm_delete_getter: Final[_Getter] = _confirm_getter(
    "msg-menu-devices-confirm-delete", "menu.device_confirm_delete"
)
device_confirm_delete_all_getter: Final[_Getter] = _confirm_getter(
    "msg-menu-devices-confirm-delete-all", "menu.device_confirm_delete_all"
)
device_confirm_reissue_getter: Final[_Getter] = _confirm_getter(
    "msg-menu-devices-confirm-reissue", "menu.device_confirm_reissue"
)


@inject
async def subscription_recurring_terms_getter(
    dialog_manager: DialogManager,
    get_own_recurring_payment: FromDishka[GetOwnRecurringPaymentUseCase],
    i18n: FromDishka[TranslatorHub],
    **kwargs: Any,
) -> dict[str, Any]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    subscription_id = selected_subscription_id(dialog_manager)
    terms = None
    if subscription_id is not None:
        state = await get_own_recurring_payment(user, subscription_id)
        terms = state.accepted_terms
    return {
        "window_text": html.escape(terms.text)
        if terms
        else runner.get("ntf-recurring.unavailable"),
        "back_text": label_with_icon(runner, "btn-back.general"),
    }

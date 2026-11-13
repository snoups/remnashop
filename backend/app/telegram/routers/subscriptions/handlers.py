from typing import Final

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.widgets.kbd import Button, Keyboard
from dishka import AsyncContainer, FromDishka
from dishka.integrations.aiogram_dialog import CONTAINER_NAME, inject
from fluentogram import TranslatorHub, TranslatorRunner

from app.core.constants import USER_KEY
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, CooldownError, NotFoundError, ValidationError
from app.modules.settings import GetShopSettingsUseCase
from app.modules.subscriptions import (
    DeleteAllDevicesUseCase,
    DeleteDeviceDto,
    DeleteDeviceUseCase,
    ListOwnActiveSubscriptionsUseCase,
    ListOwnSubscriptionsUseCase,
    ReissueSubscriptionUseCase,
    SubscriptionDto,
    SubscriptionRefDto,
)
from app.modules.transactions import (
    SetOwnRecurringPaymentUseCase,
    SetRecurringPaymentDto,
)
from app.modules.users import UserDto
from app.telegram.dialogs.context import SELECTED_SUBSCRIPTION_KEY, selected_subscription_id
from app.telegram.i18n import format_wait, get_translator
from app.telegram.notice import answer_notice
from app.telegram.states import MainMenu, Subscriptions

_GONE_CODES: Final[frozenset[ErrorCode]] = frozenset(
    {ErrorCode.SUBSCRIPTION_DELETED, ErrorCode.TARGET_SUBSCRIPTION_NOT_OWNED}
)
_RESET_DISABLED_CODES: Final[frozenset[ErrorCode]] = frozenset(
    {ErrorCode.DEVICE_RESET_DISABLED, ErrorCode.LINK_RESET_DISABLED}
)


# set by the menu's own "Devices" button, so "back" returns there
DEVICES_FROM_MENU_KEY: Final[str] = "devices_from_menu"
SINGLE_RESET_KEY: Final[str] = "single_reset_enabled"


@inject
async def on_auto_renew(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    set_recurring: FromDishka[SetOwnRecurringPaymentUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    subscription_id = selected_subscription_id(dialog_manager)
    if subscription_id is None:
        return
    if widget.widget_id not in {"auto_renew_on", "auto_renew_off"}:
        return
    try:
        result = await set_recurring(
            user,
            SetRecurringPaymentDto(
                subscription_id=subscription_id, enabled=widget.widget_id == "auto_renew_on"
            ),
        )
    except AppError:
        await answer_notice(callback, runner.get("ntf-recurring.unavailable"))
        return
    await answer_notice(
        callback,
        runner.get("ntf-recurring.enabled" if result.enabled else "ntf-recurring.disabled"),
    )


async def _only_subscription(manager: DialogManager, subscriptions: list[SubscriptionDto]) -> bool:
    """One subscription and no room for another: the list is skipped. With
    several allowed it stays, since buying one more starts there."""
    if len(subscriptions) != 1:
        return False
    container: AsyncContainer = manager.middleware_data[CONTAINER_NAME]
    get_shop_settings = await container.get(GetShopSettingsUseCase)
    return (await get_shop_settings.system()).max_active_subscriptions == 1


async def open_subscriptions(manager: DialogManager, subscriptions: list[SubscriptionDto]) -> None:
    if not subscriptions:
        await manager.start(MainMenu.MAIN, mode=StartMode.RESET_STACK)
    elif await _only_subscription(manager, subscriptions):
        await manager.start(
            Subscriptions.CARD,
            data={SELECTED_SUBSCRIPTION_KEY: subscriptions[0].id},
            mode=StartMode.RESET_STACK,
        )
    else:
        await manager.start(Subscriptions.LIST, mode=StartMode.RESET_STACK)


@inject
async def on_open_subscriptions(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await open_subscriptions(dialog_manager, await list_own_subscriptions(user))


@inject
async def on_open_devices(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    list_own_active_subscriptions: FromDishka[ListOwnActiveSubscriptionsUseCase],
) -> None:
    # the main menu's own subscription: the first active one, as its block shows
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    active = await list_own_active_subscriptions(user)
    if not active:
        await dialog_manager.start(MainMenu.MAIN, mode=StartMode.RESET_STACK)
        return
    await dialog_manager.start(
        Subscriptions.DEVICES,
        data={SELECTED_SUBSCRIPTION_KEY: active[0].id, DEVICES_FROM_MENU_KEY: True},
        mode=StartMode.RESET_STACK,
    )


async def on_devices_back(
    callback: CallbackQuery, widget: Keyboard, dialog_manager: DialogManager
) -> None:
    start = dialog_manager.start_data
    if isinstance(start, dict) and start.get(DEVICES_FROM_MENU_KEY):
        await dialog_manager.start(MainMenu.MAIN, mode=StartMode.RESET_STACK)
    else:
        await dialog_manager.switch_to(Subscriptions.CARD)


@inject
async def on_subscription_card_back(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    subscriptions = await list_own_subscriptions(user)
    # the list was skipped, so going "back" to it would reopen this card
    if await _only_subscription(dialog_manager, subscriptions):
        await dialog_manager.start(MainMenu.MAIN, mode=StartMode.RESET_STACK)
    else:
        await open_subscriptions(dialog_manager, subscriptions)


async def on_subscription_selected(
    callback: CallbackQuery, widget: Button, dialog_manager: DialogManager
) -> None:
    subscription_id = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    dialog_manager.dialog_data[SELECTED_SUBSCRIPTION_KEY] = subscription_id
    await dialog_manager.switch_to(Subscriptions.CARD)


async def _answer_cooldown(
    callback: CallbackQuery, runner: TranslatorRunner, key: str, error: CooldownError
) -> None:
    await answer_notice(callback, runner.get(key, wait=format_wait(runner, error.available_at)))


async def _subscription_gone(
    callback: CallbackQuery,
    runner: TranslatorRunner,
    dialog_manager: DialogManager,
    list_own_subscriptions: ListOwnSubscriptionsUseCase,
    user: UserDto,
) -> None:
    await answer_notice(callback, runner.get("ntf-subscription.gone"))
    await open_subscriptions(dialog_manager, await list_own_subscriptions(user))


async def _answer_refusal(
    callback: CallbackQuery,
    runner: TranslatorRunner,
    error: AppError,
    dialog_manager: DialogManager,
    list_own_subscriptions: ListOwnSubscriptionsUseCase,
    user: UserDto,
) -> None:
    if isinstance(error, NotFoundError) or error.code in _GONE_CODES:
        await _subscription_gone(callback, runner, dialog_manager, list_own_subscriptions, user)
    elif error.code in _RESET_DISABLED_CODES:
        # switched off while the window was open: redrawn without the button
        await dialog_manager.switch_to(state=Subscriptions.DEVICES)
    else:
        await answer_notice(callback, runner.get("ntf-devices.failed"))


async def on_device_delete_request(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    selected_index = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    hwid_map = dialog_manager.dialog_data.get("hwid_map", [])
    device = hwid_map[selected_index] if selected_index < len(hwid_map) else None
    if not device or not dialog_manager.dialog_data.get(SINGLE_RESET_KEY, True):
        return
    dialog_manager.dialog_data["selected_hwid"] = device["hwid"]
    await dialog_manager.switch_to(state=Subscriptions.DEVICE_CONFIRM_DELETE)


@inject
async def on_device_delete_confirm(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    delete_device: FromDishka[DeleteDeviceUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    hwid = dialog_manager.dialog_data.get("selected_hwid")
    if not hwid:
        return
    runner = get_translator(i18n, user)
    subscription_id = selected_subscription_id(dialog_manager)
    if subscription_id is None:
        await _subscription_gone(callback, runner, dialog_manager, list_own_subscriptions, user)
        return
    try:
        await delete_device(user, DeleteDeviceDto(subscription_id=subscription_id, hwid=hwid))
    except CooldownError as e:
        await _answer_cooldown(callback, runner, "ntf-devices.delete-cooldown", e)
        return
    except (NotFoundError, ValidationError) as error:
        await _answer_refusal(callback, runner, error, dialog_manager, list_own_subscriptions, user)
        return
    await answer_notice(callback, runner.get("ntf-devices.deleted"))
    await dialog_manager.switch_to(state=Subscriptions.DEVICES)


@inject
async def on_device_delete_all_confirm(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    delete_all_devices: FromDishka[DeleteAllDevicesUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    subscription_id = selected_subscription_id(dialog_manager)
    if subscription_id is None:
        await _subscription_gone(callback, runner, dialog_manager, list_own_subscriptions, user)
        return
    try:
        await delete_all_devices(user, SubscriptionRefDto(subscription_id=subscription_id))
    except CooldownError as e:
        await _answer_cooldown(callback, runner, "ntf-devices.delete-all-cooldown", e)
        return
    except (NotFoundError, ValidationError) as error:
        await _answer_refusal(callback, runner, error, dialog_manager, list_own_subscriptions, user)
        return
    await answer_notice(callback, runner.get("ntf-devices.all-deleted"))
    await dialog_manager.switch_to(state=Subscriptions.DEVICES)


@inject
async def on_reissue_subscription_confirm(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
    reissue_subscription: FromDishka[ReissueSubscriptionUseCase],
    list_own_subscriptions: FromDishka[ListOwnSubscriptionsUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    subscription_id = selected_subscription_id(dialog_manager)
    if subscription_id is None:
        await _subscription_gone(callback, runner, dialog_manager, list_own_subscriptions, user)
        return
    try:
        await reissue_subscription(user, SubscriptionRefDto(subscription_id=subscription_id))
    except CooldownError as e:
        await _answer_cooldown(callback, runner, "ntf-devices.reissue-cooldown", e)
        return
    except (NotFoundError, ValidationError) as error:
        await _answer_refusal(callback, runner, error, dialog_manager, list_own_subscriptions, user)
        return
    await answer_notice(callback, runner.get("ntf-devices.reissued"))
    await dialog_manager.switch_to(state=Subscriptions.DEVICES)

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button, Select
from aiogram_dialog.widgets.input import ManagedTextInput
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.dto import UserDto
from src.application.use_cases.settings.commands.notifications import (
    ClearSystemNotifyRoute,
    ToggleNotification,
    UpdateSystemNotifyRoute,
    UpdateSystemNotifyRouteDto,
)
from src.core.constants import USER_KEY
from src.core.enums import SystemNotificationType, UserNotificationType
from src.telegram.states import RemnashopNotifications


@inject
async def on_user_type_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_type: UserNotificationType,
    toggle_notification: FromDishka[ToggleNotification],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    await toggle_notification(user, selected_type)


async def on_system_type_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_type: str,
) -> None:
    # strip route indicator suffix if present
    clean_type = selected_type.replace(" 📡", "").strip()
    dialog_manager.dialog_data["route_ntf_type"] = clean_type
    await dialog_manager.switch_to(RemnashopNotifications.SYSTEM_TYPE)


@inject
async def on_system_type_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    toggle_notification: FromDishka[ToggleNotification],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    ntf_type = dialog_manager.dialog_data.get("route_ntf_type")
    if ntf_type:
        await toggle_notification(user, ntf_type)


async def on_system_route_edit_chat(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(RemnashopNotifications.SYSTEM_ROUTE_CHAT_ID)


async def on_system_route_edit_thread(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(RemnashopNotifications.SYSTEM_ROUTE_THREAD_ID)


@inject
async def on_route_clear(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    clear_route: FromDishka[ClearSystemNotifyRoute],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    ntf_type = dialog_manager.dialog_data.get("route_ntf_type")
    if ntf_type:
        await clear_route(user, ntf_type)
    await dialog_manager.switch_to(RemnashopNotifications.SYSTEM_ROUTE)


@inject
async def on_chat_id_entered(
    message: Message,
    widget: ManagedTextInput,
    dialog_manager: DialogManager,
    value: int,
    update_route: FromDishka[UpdateSystemNotifyRoute],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    ntf_type = dialog_manager.dialog_data.get("route_ntf_type")
    if not ntf_type:
        return

    settings_dao = await dialog_manager.middleware_data["dishka_container"].get(
        __import__("src.application.common.dao", fromlist=["SettingsDao"]).SettingsDao
    )
    settings = await settings_dao.get()
    current_route = settings.notifications.get_route(ntf_type)
    thread_id = current_route.thread_id if current_route else None

    await update_route(user, UpdateSystemNotifyRouteDto(
        notification_type=ntf_type,
        chat_id=value,
        thread_id=thread_id,
    ))
    await message.delete()
    await dialog_manager.switch_to(RemnashopNotifications.SYSTEM_ROUTE)


@inject
async def on_thread_id_entered(
    message: Message,
    widget: ManagedTextInput,
    dialog_manager: DialogManager,
    value: int,
    update_route: FromDishka[UpdateSystemNotifyRoute],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    ntf_type = dialog_manager.dialog_data.get("route_ntf_type")
    if not ntf_type:
        return

    settings_dao = await dialog_manager.middleware_data["dishka_container"].get(
        __import__("src.application.common.dao", fromlist=["SettingsDao"]).SettingsDao
    )
    settings = await settings_dao.get()
    current_route = settings.notifications.get_route(ntf_type)

    if not current_route:
        await message.answer("⚠️ Сначала укажи Chat ID")
        return

    await update_route(user, UpdateSystemNotifyRouteDto(
        notification_type=ntf_type,
        chat_id=current_route.chat_id,
        thread_id=value if value != 0 else None,
    ))
    await message.delete()
    await dialog_manager.switch_to(RemnashopNotifications.SYSTEM_ROUTE)


async def on_invalid_int(
    message: Message,
    widget: ManagedTextInput,
    dialog_manager: DialogManager,
    error: ValueError,
) -> None:
    await message.answer("⚠️ Введи целое число")

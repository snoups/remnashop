from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common.dao import SettingsDao
from src.application.common import TranslatorRunner
from src.core.enums import SystemNotificationType


@inject
async def user_types_getter(
    dialog_manager: DialogManager,
    settings_dao: FromDishka[SettingsDao],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_dao.get()

    types = [
        {
            "type": field.upper(),
            "enabled": value,
        }
        for field, value in settings.notifications.user
    ]

    return {"types": types}


@inject
async def system_types_getter(
    dialog_manager: DialogManager,
    settings_dao: FromDishka[SettingsDao],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_dao.get()

    types = []
    for field, value in settings.notifications.system:
        if field == SystemNotificationType.SYSTEM:
            continue
        has_route = settings.notifications.get_route(field) is not None
        label = i18n.get("btn-notifications.system-choice", type=field.upper(), enabled=value)
        if has_route:
            label = label + " 📡"
        types.append({
            "type": field.upper(),
            "enabled": value,
            "has_route": has_route,
            "label": label,
        })

    return {"types": types}


@inject
async def system_type_getter(
    dialog_manager: DialogManager,
    settings_dao: FromDishka[SettingsDao],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_dao.get()
    ntf_type = dialog_manager.dialog_data.get("route_ntf_type", "")
    enabled = settings.notifications.is_enabled(ntf_type)
    route = settings.notifications.get_route(ntf_type)

    ntf_label = i18n.get(
        "btn-notifications.system-choice",
        type=ntf_type.upper(),
        enabled=enabled,
    )

    route_info = "не задан (личка админам)"
    if route:
        route_info = f"chat={route.chat_id}"
        if route.thread_id:
            route_info += f", thread={route.thread_id}"

    return {
        "ntf_type": ntf_label,
        "status": "🟢 Включено" if enabled else "🔴 Выключено",
        "toggle_btn": "🔴 Выключить" if enabled else "🟢 Включить",
        "route_info": route_info,
    }


@inject
async def system_route_getter(
    dialog_manager: DialogManager,
    settings_dao: FromDishka[SettingsDao],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_dao.get()
    ntf_type = dialog_manager.dialog_data.get("route_ntf_type", "")
    route = settings.notifications.get_route(ntf_type)
    enabled = settings.notifications.is_enabled(ntf_type)

    ntf_label = i18n.get(
        "btn-notifications.system-choice",
        type=ntf_type.upper(),
        enabled=enabled,
    )

    return {
        "ntf_type": ntf_label,
        "has_route": route is not None,
        "chat_id": route.chat_id if route else "—",
        "thread_id": route.thread_id if (route and route.thread_id) else "—",
    }
from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common.dao import SettingsDao
from src.core.enums import AccessMode


@inject
async def access_getter(
    dialog_manager: DialogManager,
    settings_dao: FromDishka[SettingsDao],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_dao.get()
    current_access_mode = settings.access.mode
    available_modes = [mode for mode in AccessMode if mode != current_access_mode]

    return {
        "payments_allowed": settings.access.payments_allowed,
        "registration_allowed": settings.access.registration_allowed,
        "access_mode": current_access_mode,
        "modes": available_modes,
    }


@inject
async def conditions_getter(
    dialog_manager: DialogManager,
    settings_dao: FromDishka[SettingsDao],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_dao.get()

    return {
        "rules": settings.requirements.rules_required,
        "channel": settings.requirements.channel_required,
    }


@inject
async def rules_getter(
    dialog_manager: DialogManager,
    settings_dao: FromDishka[SettingsDao],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_dao.get()

    return {
        "rules_url": settings.requirements.rules_url,
    }


@inject
async def channel_getter(
    dialog_manager: DialogManager,
    settings_dao: FromDishka[SettingsDao],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_dao.get()

    return {
        "channel_url": settings.requirements.channel_url,
        "channel_id": settings.requirements.channel_id or False
        if not settings.requirements.channel_has_username
        else False,
    }

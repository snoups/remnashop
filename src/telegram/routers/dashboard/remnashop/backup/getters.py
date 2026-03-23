from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common.dao import SettingsDao


@inject
async def backup_getter(
    dialog_manager: DialogManager,
    settings_dao: FromDishka[SettingsDao],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_dao.get()
    backup = settings.backup

    return {
        "enabled": backup.enabled,
        "interval_hours": backup.interval_hours,
        "max_files": backup.max_files,
        "send_to_chat": backup.send_to_chat,
    }

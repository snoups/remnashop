from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.exceptions import MenuRenderingError


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        base_data = {
            "user_id": 123,
            "user_name": "name",
        }

        return base_data
    except Exception as exception:
        raise MenuRenderingError(str(exception)) from exception

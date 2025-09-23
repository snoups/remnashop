from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.services.notification import NotificationService


@inject
async def user_types_getter(
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await notification_service.get_user_settings()
    return {"types": settings.list_data}


@inject
async def system_types_getter(
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await notification_service.get_system_settings()
    return {"types": settings.list_data}

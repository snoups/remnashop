from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.core.enums import UserRole
from src.infrastructure.database.models.dto import UserDto
from src.services.user import UserService


@inject
async def admins_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    devs: list[UserDto] = await user_service.get_by_role(role=UserRole.DEV)
    admins: list[UserDto] = await user_service.get_by_role(role=UserRole.ADMIN)

    return {"admins": devs + admins}

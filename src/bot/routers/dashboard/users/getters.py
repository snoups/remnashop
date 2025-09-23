from typing import Any, cast

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.core.utils.formatters import format_percent
from src.infrastructure.database.models.dto import UserDto
from src.services.user import UserService


async def search_results_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    start_data = cast(dict[str, Any], dialog_manager.start_data)
    found_users_data: list[str] = start_data["found_users"]
    found_users: list[UserDto] = [
        UserDto.model_validate_json(json_string) for json_string in found_users_data
    ]

    return {
        "found_users": found_users,
        "count": len(found_users),
    }


@inject
async def recent_registered_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    users = await user_service.get_recent_registered_users()
    return {"recent_registered_users": users}


@inject
async def recent_activity_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    users = await user_service.get_recent_activity_users()
    return {"recent_activity_users": users}


@inject
async def blacklist_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    blocked_users = await user_service.get_blocked_users()
    count_users = await user_service.count()

    return {
        "blocked_users_exists": bool(blocked_users),
        "blocked_users": blocked_users,
        "count_blocked": len(blocked_users),
        "count_users": count_users,
        "percent": format_percent(part=len(blocked_users), whole=count_users),
    }

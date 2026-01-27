from typing import Any

from adaptix import Retort
from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common.dao import UserDao
from src.application.dto import UserDto
from src.core.utils.converters import percent


@inject
async def search_results_getter(
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    **kwargs: Any,
) -> dict[str, Any]:
    found_users_data: list[str] = dialog_manager.start_data["found_users"]  # type: ignore[call-overload, index, assignment]
    found_users: list[UserDto] = retort.load(found_users_data, list[UserDto])

    return {
        "found_users": found_users,
        "count": len(found_users),
    }


@inject
async def recent_registered_getter(
    dialog_manager: DialogManager,
    user_dao: FromDishka[UserDao],
    **kwargs: Any,
) -> dict[str, Any]:
    users = await user_dao.get_recent_registered_users()
    return {"recent_registered_users": users}


@inject
async def recent_activity_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    user_dao: FromDishka[UserDao],
    **kwargs: Any,
) -> dict[str, Any]:
    users = await user_dao.get_recent_activity_users(excluded_ids=[user.telegram_id])
    return {"recent_activity_users": users}


@inject
async def blacklist_getter(
    dialog_manager: DialogManager,
    user_dao: FromDishka[UserDao],
    **kwargs: Any,
) -> dict[str, Any]:
    blocked_users = await user_dao.get_blocked_users()
    count_users = await user_dao.count()

    return {
        "blocked_users_exists": bool(blocked_users),
        "blocked_users": blocked_users,
        "count_blocked": len(blocked_users),
        "count_users": count_users,
        "percent": percent(part=len(blocked_users), whole=count_users),
    }

from typing import Any

from adaptix import Retort
from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.dto import UserDto
from src.application.use_cases.user import GetAdmins, GetAdminsResultDto
from src.core.config import AppConfig


async def remnashop_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    **kwargs: Any,
) -> dict[str, Any]:
    return {"version": config.build.tag}


@inject
async def admins_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    retort: FromDishka[Retort],
    get_admins: FromDishka[GetAdmins],
    **kwargs: Any,
) -> dict[str, Any]:
    admins = await get_admins(user)
    return {"admins": retort.dump(admins, list[GetAdminsResultDto])}

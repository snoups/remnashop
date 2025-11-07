from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from remnawave import RemnawaveSDK
from remnawave.models import GetAllInternalSquadsResponseDto


async def from_xui_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    users = dialog_manager.dialog_data.get("users")
    has_started = dialog_manager.dialog_data.get("has_started", False)

    if not users:
        return {"has_exported": False}

    return {
        "has_exported": True,
        "has_started": has_started,
        "total": len(users["all"]),
        "active": len(users["active"]),
        "expired": len(users["expired"]),
    }


@inject
async def squads_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    response = await remnawave.internal_squads.get_internal_squads()
    selected_squads = dialog_manager.dialog_data.get("selected_squads", [])

    if not isinstance(response, GetAllInternalSquadsResponseDto):
        raise ValueError("Wrong response from Remnawave")

    squads = [
        {
            "uuid": str(squad.uuid),
            "name": squad.name,
            "selected": True if str(squad.uuid) in selected_squads else False,
        }
        for squad in response.internal_squads
    ]

    return {"squads": squads}


@inject
async def import_completed_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    completed: dict = dialog_manager.dialog_data["completed"]
    return completed


async def sync_completed_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    completed: dict = dialog_manager.dialog_data["completed"]
    return completed

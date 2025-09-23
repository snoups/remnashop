from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.infrastructure.database.models.dto import UserDto
from src.services.maintenance import MaintenanceService


async def dashboard_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "is_dev": user.is_dev,
    }


@inject
async def maintenance_getter(
    dialog_manager: DialogManager,
    maintenance_service: FromDishka[MaintenanceService],
    **kwargs: Any,
) -> dict[str, Any]:
    current_mode = await maintenance_service.get_current_mode()
    modes = await maintenance_service.get_available_modes()

    return {
        "status": current_mode,
        "modes": modes,
    }

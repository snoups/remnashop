from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.core.constants import USER_KEY
from src.core.enums import MaintenanceMode
from src.core.utils.formatters import format_log_user
from src.infrastructure.database.models.dto import UserDto
from src.services.maintenance import MaintenanceService


@inject
async def on_maintenance_mode_selected(
    callback: CallbackQuery,
    widget: Select[MaintenanceMode],
    dialog_manager: DialogManager,
    selected_mode: MaintenanceMode,
    maintenance_service: FromDishka[MaintenanceService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    await maintenance_service.set_mode(mode=selected_mode)
    logger.info(f"{format_log_user(user)} Set maintenance mode -> '{selected_mode}'")

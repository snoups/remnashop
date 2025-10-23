from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.bot.keyboards import goto_buttons
from src.core.constants import DATETIME_FORMAT
from src.infrastructure.database.models.dto import PlanDto
from src.services.broadcast import BroadcastService
from src.services.plan import PlanService


@inject
async def plans_getter(
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    plans: list[PlanDto] = await plan_service.get_all()
    formatted_plans = [
        {
            "id": plan.id,
            "name": plan.name,
            "is_active": plan.is_active,
        }
        for plan in plans
    ]

    return {
        "plans": formatted_plans,
    }


async def send_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    audience = dialog_manager.dialog_data["audience_type"]
    audience_count: int = dialog_manager.dialog_data["audience_count"]

    return {
        "audience_type": audience,
        "audience_count": audience_count,
    }


async def buttons_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    buttons = dialog_manager.dialog_data.get("buttons", [])

    if not buttons:
        buttons = [
            {
                "id": index,
                "text": goto_button.text,
                "selected": False,
            }
            for index, goto_button in enumerate(goto_buttons)
        ]
        dialog_manager.dialog_data["buttons"] = buttons

    return {
        "buttons": buttons,
    }


@inject
async def list_getter(
    dialog_manager: DialogManager,
    broadcast_service: FromDishka[BroadcastService],
    **kwargs: Any,
) -> dict[str, Any]:
    broadcasts = await broadcast_service.get_all()

    formatted_broadcasts = [
        {
            "task_id": broadcast.task_id,
            "status": broadcast.status,
            "created_at": broadcast.created_at.strftime(DATETIME_FORMAT),  # type: ignore[union-attr]
        }
        for broadcast in broadcasts
    ]

    return {"broadcasts": formatted_broadcasts}


@inject
async def view_getter(
    dialog_manager: DialogManager,
    broadcast_service: FromDishka[BroadcastService],
    **kwargs: Any,
) -> dict[str, Any]:
    task_id = dialog_manager.dialog_data.get("task_id")

    if not task_id:
        raise ValueError("Task ID not found in dialog data")

    broadcast = await broadcast_service.get(task_id)

    if not broadcast:
        raise ValueError(f"Broadcast '{task_id}' not found")

    dialog_manager.dialog_data["payload"] = broadcast.payload.model_dump()

    return {
        "id": str(broadcast.task_id),
        "broadcast_status": broadcast.status,
        "audience_type": broadcast.audience,
        "created_at": broadcast.created_at.strftime(DATETIME_FORMAT),  # type: ignore[union-attr]
        "total_count": broadcast.total_count,
        "success_count": broadcast.success_count,
        "failed_count": broadcast.failed_count,
    }

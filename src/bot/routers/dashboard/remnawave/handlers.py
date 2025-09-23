from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger
from remnawave import RemnawaveSDK

from src.bot.states import DashboardRemnawave
from src.core.constants import USER_KEY
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService


@inject
async def start_remnawave_window(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    try:
        response = await remnawave.system.get_stats()
    except Exception as exception:
        logger.error(f"Remnawave: {exception}")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error-connect-remnawave"),
        )
        return

    await dialog_manager.start(state=DashboardRemnawave.MAIN, mode=StartMode.RESET_STACK)

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.bot.states import DashboardUsers
from src.core.constants import USER_KEY
from src.core.utils.formatters import format_log_user
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.user import UserService

from .user.handlers import start_user_window


@inject
async def on_user_search(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    user_service: FromDishka[UserService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if not user.is_privileged:
        return

    found_users = await user_service.search_users(message)

    if not found_users:
        search_query = message.text.strip() if message.text else None
        logger.info(f"{format_log_user(user)} User search for '{search_query}' yielded no results")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-not-found"),
        )
    elif len(found_users) == 1:
        target_user = found_users[0]
        logger.info(
            f"{format_log_user(user)} Successfully searched "
            f"for single user {format_log_user(target_user)}"
        )
        await start_user_window(manager=dialog_manager, target_telegram_id=target_user.telegram_id)
    else:
        search_query = message.text.strip() if message.text else None
        logger.info(
            f"{format_log_user(user)} User search for '{search_query}' "
            f"found {len(found_users)} results. Proceeding to selection state"
        )
        await dialog_manager.start(
            state=DashboardUsers.SEARCH_RESULTS,
            data={"found_users": [found_user.model_dump_json() for found_user in found_users]},
        )


async def on_user_selected(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    user_selected: int,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    logger.debug(f"{format_log_user(user)} User '{user_selected}' selected")
    await start_user_window(manager=dialog_manager, target_telegram_id=user_selected)


@inject
async def on_unblock_all(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    blocked_users = await user_service.get_blocked_users()

    for blocked_user in blocked_users:
        await user_service.set_block(user=blocked_user, blocked=False)

    logger.warning(f"{format_log_user(user)} Unblocked all users")
    await dialog_manager.start(state=DashboardUsers.BLACKLIST, mode=StartMode.RESET_STACK)

from adaptix import Retort
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Notifier
from src.application.dto import UserDto
from src.application.use_cases.user import SearchUsers, SearchUsersDto, UnblockAllUsers
from src.core.constants import USER_KEY
from src.telegram.states import DashboardUsers
from src.telegram.utils import is_double_click

from .user.handlers import start_user_window


@inject
async def on_user_search(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    notifier: FromDishka[Notifier],
    search_users: FromDishka[SearchUsers],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    search_data = SearchUsersDto(
        query=message.text,
        forward_from_id=message.forward_from.id if message.forward_from else None,
        is_forwarded_from_bot=message.forward_from.is_bot if message.forward_from else False,
    )

    found_users = await search_users(user, search_data)
    search_query = message.text.strip() if message.text else "forwarded_msg"

    if not found_users:
        logger.info(f"{user.log} Search for '{search_query}' yielded no results")
        await notifier.notify_user(user, i18n_key="ntf-user.not-found")

    elif len(found_users) == 1:
        target_user = found_users[0]
        logger.info(f"{user.log} Searched user -> {target_user.log}")
        await start_user_window(manager=dialog_manager, target_telegram_id=target_user.telegram_id)

    else:
        logger.info(f"{user.log} Search for '{search_query}' found '{len(found_users)}' results")
        await dialog_manager.start(
            state=DashboardUsers.SEARCH_RESULTS,
            data={"found_users": retort.dump(found_users, list[UserDto])},
        )


async def on_user_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_user: int,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{user.log} User id '{selected_user}' selected")
    await start_user_window(manager=dialog_manager, target_telegram_id=selected_user)


@inject
async def on_unblock_all(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    unblock_all: FromDishka[UnblockAllUsers],
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if is_double_click(dialog_manager, key="unblock_all_confirm", cooldown=5):
        count = await unblock_all(user)

        if count > 0:
            await notifier.notify_user(user, i18n_key="ntf-all-users-unblocked")

        await dialog_manager.start(state=DashboardUsers.BLACKLIST, mode=StartMode.RESET_STACK)
        return

    await notifier.notify_user(user, i18n_key="ntf-common.double-click-confirm")
    logger.debug(f"{user.log} Awaiting confirmation to unblock all users")

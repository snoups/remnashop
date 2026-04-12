from adaptix import Retort
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Notifier
from src.application.common.policy import Permission, PermissionPolicy
from src.application.dto import MessagePayloadDto, UserDto
from src.application.use_cases.user.queries.search import SearchUsersDto, SmartSearch
from src.core.constants import USER_KEY
from src.telegram.keyboards import get_boosty_keyboard
from src.telegram.states import DashboardUsers

from .users.user.handlers import start_user_transaction_window, start_user_window


@inject
async def show_dev_promocode(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    await notifier.notify_user(
        user,
        MessagePayloadDto(
            i18n_key="development-promocode",
            reply_markup=get_boosty_keyboard(),
            disable_default_markup=False,
            delete_after=None,
        ),
    )


@inject
async def on_smart_search(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    notifier: FromDishka[Notifier],
    smart_search: FromDishka[SmartSearch],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if not PermissionPolicy.has_permission(user, Permission.USER_SEARCH):
        return

    search_data = SearchUsersDto(
        query=message.text,
        forward_from_id=message.forward_from.id if message.forward_from else None,
        forward_sender_name=message.forward_sender_name if message.forward_sender_name else None,
        is_forwarded_from_bot=message.forward_from.is_bot if message.forward_from else False,
    )

    result = await smart_search(user, search_data)

    if result.found_transaction:
        transaction = result.transaction
        logger.info(f"{user.log} Smart search: transaction '{transaction.payment_id}' -> user '{transaction.user_telegram_id}'")  # type: ignore[union-attr]
        await start_user_transaction_window(
            manager=dialog_manager,
            target_telegram_id=transaction.user_telegram_id,  # type: ignore[union-attr]
            selected_transaction=transaction.payment_id,  # type: ignore[union-attr]
        )
        return

    if result.transaction_searched:
        await notifier.notify_user(user, i18n_key="ntf-user.transaction-not-found")
        return

    found_users = result.users

    if not found_users:
        await notifier.notify_user(user, i18n_key="ntf-user.not-found")

    elif len(found_users) == 1:
        target_user = found_users[0]
        logger.info(f"{user.log} Smart search -> {target_user.log}")
        await start_user_window(manager=dialog_manager, target_telegram_id=target_user.telegram_id)

    else:
        await dialog_manager.start(
            state=DashboardUsers.SEARCH_RESULTS,
            data={"found_users": retort.dump(found_users, list[UserDto])},
        )

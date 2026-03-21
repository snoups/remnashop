from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common import Notifier
from src.application.dto import MessagePayloadDto, UserDto
from src.core.constants import USER_KEY
from src.telegram.keyboards import get_boosty_keyboard


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

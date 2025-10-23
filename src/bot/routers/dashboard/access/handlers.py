from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger
from pydantic import SecretStr

from src.bot.states import DashboardAccess
from src.core.constants import USER_KEY
from src.core.enums import AccessMode
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.core.utils.validators import _is_valid_url, _is_valid_username
from src.infrastructure.database.models.dto import UserDto
from src.services.access import AccessService
from src.services.notification import NotificationService
from src.services.settings import SettingsService


@inject
async def on_access_mode_select(
    callback: CallbackQuery,
    widget: Select[AccessMode],
    dialog_manager: DialogManager,
    selected_mode: AccessMode,
    access_service: FromDishka[AccessService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    logger.info(f"{log(user)} Set access mode -> '{selected_mode}'")
    await access_service.set_mode(mode=selected_mode)


@inject
async def on_condition_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()

    if callback.data == "rules":
        new_state = not settings.rules_required
        settings.rules_required = new_state

    if callback.data == "channel":
        new_state = not settings.channel_required
        settings.channel_required = new_state

    await settings_service.update(settings)
    logger.info(f"{log(user)} Toggled {callback.data} -> '{new_state}'")


@inject
async def on_rules_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to set rules link")
    input_text: str = message.text.strip() if message.text else ""

    if not _is_valid_url(input_text):
        logger.warning(f"{log(user)} Provided invalid rules link format: {input_text}")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-access-invalid-link"),
        )
        return

    settings = await settings_service.get()
    settings.rules_link = SecretStr(input_text)
    await settings_service.update(settings)

    logger.info(f"{log(user)} Successfully set rules link")
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-access-link-saved"),
    )
    await dialog_manager.switch_to(state=DashboardAccess.CONDITIONS)


@inject
async def on_channel_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to set channel link")
    input_text: str = message.text.strip() if message.text else ""

    if not _is_valid_username(input_text):
        logger.warning(f"{log(user)} Provided invalid channel link format: {input_text}")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-access-invalid-link"),
        )
        return

    settings = await settings_service.get()
    settings.channel_link = SecretStr(input_text)
    await settings_service.update(settings)

    logger.info(f"{log(user)} Successfully set channel link")
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-access-link-saved"),
    )
    await dialog_manager.switch_to(state=DashboardAccess.CONDITIONS)

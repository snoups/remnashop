from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger
from pydantic import SecretStr

from src.bot.states import DashboardAccess
from src.core.constants import T_ME, USER_KEY
from src.core.enums import AccessMode
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.core.utils.validators import is_valid_url, is_valid_username
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
async def on_purchases_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()

    new_state = not settings.purchases_allowed
    settings.purchases_allowed = new_state

    await settings_service.update(settings)
    logger.info(f"{log(user)} Toggled purchases allowed -> '{new_state}'")


@inject
async def on_registration_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()

    new_state = not settings.registration_allowed
    settings.registration_allowed = new_state

    await settings_service.update(settings)
    logger.info(f"{log(user)} Toggled registration allowed -> '{new_state}'")


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
    logger.info(f"{log(user)} Toggled '{callback.data}' -> '{new_state}'")


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

    if not is_valid_url(input_text):
        logger.warning(f"{log(user)} Provided invalid rules link format: '{input_text}'")
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
    settings = await settings_service.get()

    if input_text.isdigit():
        channel_id = int(input_text)
        if not input_text.startswith("-100"):
            channel_id = int(f"-100{input_text}")
        settings.channel_id = channel_id
        logger.info(f"{log(user)} Saved channel ID: {channel_id}")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-access-id-saved"),
        )

    elif input_text.startswith("-100") and input_text[1:].isdigit():
        settings.channel_id = int(input_text)
        logger.info(f"{log(user)} Saved channel ID: {input_text}")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-access-id-saved"),
        )

    elif is_valid_username(input_text) or input_text.startswith(T_ME):
        settings.channel_link = SecretStr(input_text)
        logger.info(f"{log(user)} Saved channel link: '{input_text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-access-link-saved"),
        )

    else:
        logger.warning(f"{log(user)} Provided invalid channel input: '{input_text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-access-channel-invalid"),
        )
        return

    await settings_service.update(settings)

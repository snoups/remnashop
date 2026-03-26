from adaptix import Retort
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Notifier
from src.application.dto import MenuButtonDto, UserDto
from src.application.use_cases.misc.commands.menu_editor import (
    ConfirmMenuButtonChanges,
    UpdateMenuButtonPayload,
    UpdateMenuButtonPayloadDto,
    UpdateMenuButtonText,
    UpdateMenuButtonTextDto,
)
from src.core.constants import USER_KEY
from src.core.enums import ButtonType, Role
from src.core.exceptions import MenuEditorInvalidPayloadError
from src.telegram.states import RemnashopMenuEditor


async def on_button_selected(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_button_id: int,
) -> None:
    buttons = dialog_manager.dialog_data["buttons"]
    selected_button = next((b for b in buttons if b["index"] == selected_button_id), None)
    dialog_manager.dialog_data["button"] = selected_button
    await dialog_manager.switch_to(RemnashopMenuEditor.BUTTON)


@inject
async def on_active_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    button = dialog_manager.dialog_data["button"]
    button = retort.load(button, MenuButtonDto)

    old_status = button.is_active
    button.is_active = not button.is_active
    dialog_manager.dialog_data["button"] = retort.dump(button)

    logger.info(
        f"{user.log} Updated menu button '{button.index}' "
        f"active status from '{old_status}' to '{button.is_active}'"
    )


@inject
async def on_text_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    notifier: FromDishka[Notifier],
    update_menu_button_text: FromDishka[UpdateMenuButtonText],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if message.text is None:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    button = dialog_manager.dialog_data["button"]
    button = retort.load(button, MenuButtonDto)

    try:
        button = await update_menu_button_text(user, UpdateMenuButtonTextDto(button, message.text))
    except ValueError:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    dialog_manager.dialog_data["button"] = retort.dump(button)
    await dialog_manager.switch_to(RemnashopMenuEditor.BUTTON)


@inject
async def on_availability_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_availability: int,
    retort: FromDishka[Retort],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    button = dialog_manager.dialog_data["button"]
    button = retort.load(button, MenuButtonDto)

    old_role = button.required_role
    button.required_role = Role(selected_availability)
    dialog_manager.dialog_data["button"] = retort.dump(button)

    logger.info(
        f"{user.log} Updated menu button '{button.index}' "
        f"required role from '{old_role}' to '{button.required_role}'"
    )

    await dialog_manager.switch_to(RemnashopMenuEditor.BUTTON)


@inject
async def on_type_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_type: ButtonType,
    retort: FromDishka[Retort],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    button = dialog_manager.dialog_data["button"]
    button = retort.load(button, MenuButtonDto)

    old_type = button.type
    button.type = selected_type
    dialog_manager.dialog_data["button"] = retort.dump(button)

    logger.info(
        f"{user.log} Updated menu button '{button.index}' type from '{old_type}' to '{button.type}'"
    )

    await dialog_manager.switch_to(RemnashopMenuEditor.BUTTON)


@inject
async def on_payload_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    notifier: FromDishka[Notifier],
    update_menu_button_payload: FromDishka[UpdateMenuButtonPayload],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if message.text is None:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    button = dialog_manager.dialog_data["button"]
    button = retort.load(button, MenuButtonDto)

    try:
        button = await update_menu_button_payload(
            user, UpdateMenuButtonPayloadDto(button, message.text)
        )
    except ValueError:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    dialog_manager.dialog_data["button"] = retort.dump(button)
    await dialog_manager.switch_to(RemnashopMenuEditor.BUTTON)


@inject
async def on_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    notifier: FromDishka[Notifier],
    confirm_menu_button_changes: FromDishka[ConfirmMenuButtonChanges],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    button = dialog_manager.dialog_data["button"]
    button = retort.load(button, MenuButtonDto)

    try:
        await confirm_menu_button_changes(user, button)
    except MenuEditorInvalidPayloadError:
        await notifier.notify_user(user, i18n_key="ntf-menu-editor.invalid-payload")

    await notifier.notify_user(user, i18n_key="ntf-menu-editor.button-saved")
    await dialog_manager.reset_stack()
    await dialog_manager.start(state=RemnashopMenuEditor.MAIN)

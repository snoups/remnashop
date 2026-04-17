import re
from dataclasses import dataclass
from typing import Optional

from aiogram.enums import ButtonStyle
from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import SettingsDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import MenuButtonDto, UserDto
from src.core.constants import T_ME, TEXT_MAX_LENGTH, TEXT_MEDIA_MAX_LENGTH, URL_PATTERN
from src.core.enums import ButtonType, MediaType
from src.core.exceptions import MenuEditorInvalidPayloadError


@dataclass(frozen=True)
class UpdateMenuButtonTextDto:
    button: MenuButtonDto
    input_text: str


class UpdateMenuButtonText(Interactor[UpdateMenuButtonTextDto, MenuButtonDto]):
    required_permission = Permission.SETTINGS_MENU

    async def _execute(self, actor: UserDto, data: UpdateMenuButtonTextDto) -> MenuButtonDto:
        button = data.button
        new_text = data.input_text.strip()

        if len(new_text) > 32:
            raise ValueError(f"Menu button text '{new_text}' exceeds 32 characters")

        old_text = button.text
        button.text = new_text

        logger.info(
            f"{actor.log} Updated menu button '{button.index}' "
            f"text from '{old_text}' to '{new_text}'"
        )

        return button


@dataclass(frozen=True)
class UpdateMenuButtonPayloadDto:
    button: MenuButtonDto
    input_payload: str


class UpdateMenuButtonPayload(Interactor[UpdateMenuButtonPayloadDto, MenuButtonDto]):
    required_permission = Permission.SETTINGS_MENU

    async def _execute(self, actor: UserDto, data: UpdateMenuButtonPayloadDto) -> MenuButtonDto:
        button = data.button
        new_payload = data.input_payload.strip()

        if button.type in [ButtonType.URL, ButtonType.WEB_APP]:
            if not re.compile(r"^https://.*$").match(new_payload):
                raise ValueError(f"Invalid URL format for payload '{new_payload}'")

        if button.type == ButtonType.WEB_APP and T_ME in new_payload:
            raise ValueError(f"Telegram links are not allowed for WebApp buttons: '{new_payload}'")

        if button.type == ButtonType.TEXT:
            max_length = TEXT_MAX_LENGTH if button.media_file_id else TEXT_MEDIA_MAX_LENGTH
            if len(new_payload) > max_length:
                raise ValueError(f"Text message exceeds {max_length} characters")

        old_payload = button.payload
        button.payload = new_payload

        logger.info(
            f"{actor.log} Updated menu button '{button.index}' "
            f"payload from '{old_payload}' to '{new_payload}'"
        )

        return button


class ConfirmMenuButtonChanges(Interactor[MenuButtonDto, None]):
    required_permission = Permission.SETTINGS_MENU

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, button: MenuButtonDto) -> None:
        if button.type in (ButtonType.URL, ButtonType.WEB_APP):
            if button.payload and not URL_PATTERN.match(button.payload):
                raise MenuEditorInvalidPayloadError(
                    f"Invalid URL format for payload '{button.payload}'"
                )

        if button.type == ButtonType.WEB_APP and button.payload and T_ME in button.payload:
            raise MenuEditorInvalidPayloadError(
                f"Telegram links are not allowed for WebApp buttons: '{button.payload}'"
            )

        if button.type == ButtonType.TEXT and button.payload:
            max_length = TEXT_MAX_LENGTH if button.media_file_id else TEXT_MEDIA_MAX_LENGTH
            if len(button.payload) > max_length:
                raise MenuEditorInvalidPayloadError(
                    f"Text message exceeds {max_length} characters"
                )

        settings = await self.settings_dao.get()

        async with self.uow:
            settings.menu.buttons = [
                button if b.index == button.index else b for b in settings.menu.buttons
            ]
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Confirmed and saved changes for menu button '{button.index}'")


@dataclass(frozen=True)
class UpdateMenuButtonColorDto:
    button: MenuButtonDto
    input_color: Optional[ButtonStyle]


class UpdateMenuButtonColor(Interactor[UpdateMenuButtonColorDto, MenuButtonDto]):
    required_permission = Permission.SETTINGS_MENU

    async def _execute(self, actor: UserDto, data: UpdateMenuButtonColorDto) -> MenuButtonDto:
        button = data.button
        new_color = data.input_color

        old_color = button.color
        button.color = new_color

        logger.info(
            f"{actor.log} Updated menu button '{button.index}' "
            f"color from '{old_color!r}' to '{new_color!r}'"
        )

        return button


@dataclass(frozen=True)
class UpdateMenuButtonMediaDto:
    button: MenuButtonDto
    file_id: Optional[str]
    media_type: Optional[MediaType]


class UpdateMenuButtonMedia(Interactor[UpdateMenuButtonMediaDto, MenuButtonDto]):
    required_permission = Permission.SETTINGS_MENU

    async def _execute(self, actor: UserDto, data: UpdateMenuButtonMediaDto) -> MenuButtonDto:
        button = data.button
        button.media_file_id = data.file_id
        button.media_type = data.media_type

        logger.info(
            f"{actor.log} Updated menu button '{button.index}' "
            f"media to file_id='{data.file_id}' type='{data.media_type}'"
        )

        return button

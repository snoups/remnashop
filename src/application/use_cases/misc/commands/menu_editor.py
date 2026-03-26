import re
from dataclasses import dataclass

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import SettingsDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import MenuButtonDto, UserDto
from src.core.constants import URL_PATTERN
from src.core.enums import ButtonType
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

        if len(new_text) > 16:
            raise ValueError(f"Menu button text '{new_text}' exceeds 16 characters")

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

        old_payload = button.payload
        button.payload = new_payload

        logger.info(
            f"{actor.log} Updated menu button '{button.index}' "
            f"payload from '{old_payload}' to '{new_payload}'"
        )

        return button


class ConfirmMenuButtonChanges(Interactor[MenuButtonDto, None]):
    required_permission = Permission.SETTINGS_MENU

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao):
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, button: MenuButtonDto) -> None:
        if button.type in (ButtonType.URL, ButtonType.WEB_APP):
            if button.payload and not URL_PATTERN.match(button.payload):
                raise MenuEditorInvalidPayloadError(
                    f"Invalid URL format for payload '{button.payload}'"
                )

        settings = await self.settings_dao.get()

        async with self.uow:
            settings.menu.buttons = [
                button if b.index == button.index else b for b in settings.menu.buttons
            ]
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Confirmed and saved changes for menu button '{button.index}'")

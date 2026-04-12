from loguru import logger
from pydantic import SecretStr

from src.application.common import Interactor, Notifier
from src.application.common.dao import SettingsDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import SettingsDto, UserDto
from src.core.constants import T_ME
from src.core.enums import AccessRequirements
from src.core.utils.validators import is_valid_url, is_valid_username


class ToggleConditionRequirement(Interactor[AccessRequirements, None]):
    required_permission = Permission.SETTINGS_REQUIREMENT

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao) -> None:
        self.uow = uow
        self.settings_dao = settings_dao

    async def _execute(self, actor: UserDto, condition_type: AccessRequirements) -> None:
        async with self.uow:
            settings = await self.settings_dao.get()

            if condition_type == AccessRequirements.RULES:
                settings.requirements.rules_required = not settings.requirements.rules_required
                new_state = settings.requirements.rules_required
            elif condition_type == AccessRequirements.CHANNEL:
                settings.requirements.channel_required = not settings.requirements.channel_required
                new_state = settings.requirements.channel_required
            else:
                logger.error(f"{actor.log} Tried to toggle unknown condition '{condition_type}'")
                return

            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Toggled access requirement '{condition_type}' to '{new_state}'")


class UpdateRulesRequirement(Interactor[str, bool]):
    required_permission = Permission.SETTINGS_REQUIREMENT

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao, notifier: Notifier) -> None:
        self.uow = uow
        self.settings_dao = settings_dao
        self.notifier = notifier

    async def _execute(self, actor: UserDto, input_text: str) -> bool:
        input_text = input_text.strip()

        if not is_valid_url(input_text):
            logger.warning(f"{actor.log} Provided invalid rules url format: '{input_text}'")
            await self.notifier.notify_user(actor, i18n_key="ntf-common.invalid-value")
            return False

        settings = await self.settings_dao.get()
        settings.requirements.rules_link = SecretStr(input_text)

        async with self.uow:
            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Successfully updated rules url")
        await self.notifier.notify_user(actor, i18n_key="ntf-common.value-updated")
        return True


class UpdateChannelRequirement(Interactor[str, None]):
    required_permission = Permission.SETTINGS_REQUIREMENT

    def __init__(self, uow: UnitOfWork, settings_dao: SettingsDao, notifier: Notifier) -> None:
        self.uow = uow
        self.settings_dao = settings_dao
        self.notifier = notifier

    async def _execute(self, actor: UserDto, input_text: str) -> None:
        input_text = input_text.strip()

        async with self.uow:
            settings = await self.settings_dao.get()

            if input_text.isdigit() or (input_text.startswith("-") and input_text[1:].isdigit()):
                await self._handle_id_input(input_text, settings)
                await self.notifier.notify_user(actor, i18n_key="ntf-common.value-updated")
            elif is_valid_username(input_text) or input_text.startswith(T_ME):
                settings.requirements.channel_link = SecretStr(input_text)
                await self.notifier.notify_user(actor, i18n_key="ntf-common.value-updated")
            else:
                logger.warning(f"{actor.log} Provided invalid channel format: '{input_text}'")
                await self.notifier.notify_user(actor, i18n_key="ntf-common.invalid-value")

            await self.settings_dao.update(settings)
            await self.uow.commit()

        logger.info(f"{actor.log} Updated channel requirement")

    async def _handle_id_input(self, text: str, settings: SettingsDto) -> None:
        channel_id = int(text)
        if not text.startswith("-100") and not text.startswith("-"):
            channel_id = int(f"-100{text}")

        settings.requirements.channel_id = channel_id

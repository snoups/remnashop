from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import BotSettingsDto, UpdateBotSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


class UpdateBotSettingsUseCase(UseCase[UpdateBotSettingsDto, BotSettingsDto]):
    required_permission = Permission.BOT_SETTINGS_MANAGE

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdateBotSettingsDto) -> BotSettingsDto:
        async with self._uow:
            settings = await self._settings_repository.update_bot_settings(data)
        logger.info(f"Bot settings updated by actor {actor.log}")
        return settings

from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import BotSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


class GetBotSettingsUseCase(UseCase[None, BotSettingsDto]):
    required_permission = Permission.BOT_SETTINGS_VIEW

    def __init__(self, settings_repository: SettingsRepository) -> None:
        self._settings_repository = settings_repository

    async def _execute(self, actor: UserDto, data: None) -> BotSettingsDto:
        return await self._settings_repository.get_bot_settings()

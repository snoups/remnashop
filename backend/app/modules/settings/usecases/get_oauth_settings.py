from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import OAuthSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


class GetOAuthSettingsUseCase(UseCase[None, OAuthSettingsDto]):
    required_permission = Permission.OAUTH_SETTINGS_VIEW

    def __init__(self, settings_repository: SettingsRepository) -> None:
        self._settings_repository = settings_repository

    async def _execute(self, actor: UserDto, data: None) -> OAuthSettingsDto:
        return await self._settings_repository.get_oauth_settings()

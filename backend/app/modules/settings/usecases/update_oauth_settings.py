from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.http import assert_public_https_host
from app.modules.settings.dto import OAuthSettingsDto, UpdateOAuthSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


class UpdateOAuthSettingsUseCase(UseCase[UpdateOAuthSettingsDto, OAuthSettingsDto]):
    required_permission = Permission.OAUTH_SETTINGS_MANAGE

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdateOAuthSettingsDto) -> OAuthSettingsDto:
        if data.oidc_issuer_url is not None:
            await assert_public_https_host(data.oidc_issuer_url)

        async with self._uow:
            settings = await self._settings_repository.update_oauth_settings(data)
        return settings

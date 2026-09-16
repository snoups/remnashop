from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider, Role
from app.modules.auth.dto import AuthStatusDto
from app.modules.settings import SettingsRepository
from app.modules.users import UserRepository


class GetAuthStatusUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._settings_repository = settings_repository
        self._uow = uow

    async def execute(self) -> AuthStatusDto:
        async with self._uow:
            owner_exists = await self._user_repository.exists_with_role(Role.OWNER)
            oauth_settings = await self._settings_repository.get_oauth_settings()
            return AuthStatusDto(
                owner_exists=owner_exists,
                oauth_providers={
                    OAuthProvider.GITHUB: oauth_settings.is_github_usable,
                    OAuthProvider.TELEGRAM: oauth_settings.is_telegram_usable,
                    OAuthProvider.OIDC: oauth_settings.is_oidc_usable,
                },
                oidc_display_name=(
                    oauth_settings.oidc_display_name if oauth_settings.is_oidc_usable else None
                ),
                password_login_enabled=oauth_settings.password_login_enabled,
                is_passkey_login_enabled=oauth_settings.is_passkey_usable,
            )

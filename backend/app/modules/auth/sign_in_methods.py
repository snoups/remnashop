from typing import Optional

from app.core.enums import OAuthProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.modules.auth.ports import PasskeyCounter
from app.modules.settings import SettingsRepository
from app.modules.users import OAuthIdentityLookup, UserDto


class SignInMethodGuard:
    """Refuses to take away a staff account's last way into the dashboard."""

    def __init__(
        self,
        settings_repository: SettingsRepository,
        oauth_identities: OAuthIdentityLookup,
        passkeys: PasskeyCounter,
    ) -> None:
        self._settings_repository = settings_repository
        self._oauth_identities = oauth_identities
        self._passkeys = passkeys

    async def assert_one_left(
        self,
        user: UserDto,
        *,
        without_provider: Optional[OAuthProvider] = None,
        without_passkey: bool = False,
    ) -> None:
        settings = await self._settings_repository.get_oauth_settings()
        if settings.password_login_enabled and user.login and user.password_hash:
            return
        if (
            settings.is_telegram_usable
            and user.telegram_id is not None
            and without_provider is not OAuthProvider.TELEGRAM
        ):
            return
        providers = {
            provider
            for provider, usable in (
                (OAuthProvider.GITHUB, settings.is_github_usable),
                (OAuthProvider.OIDC, settings.is_oidc_usable),
            )
            if usable and provider is not without_provider
        }
        if providers and await self._oauth_identities.user_ids_with_identities(
            [user.id], providers
        ):
            return
        if settings.is_passkey_usable:
            left = await self._passkeys.count_by_user(user.id) - (1 if without_passkey else 0)
            if left > 0:
                return
        raise ConflictError(
            f"User '{user.id}' would have no way left to sign in",
            code=ErrorCode.LAST_SIGN_IN_METHOD,
        )

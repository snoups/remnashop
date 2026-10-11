from typing import Optional

from app.core.enums import OAuthProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.oauth.providers.base import OAuthProviderClient
from app.modules.oauth.providers.github import GitHubOAuthClient
from app.modules.oauth.providers.google import GoogleOAuthClient
from app.modules.oauth.providers.oidc import OIDCOAuthClient
from app.modules.oauth.providers.telegram import TelegramOAuthClient
from app.modules.oauth.providers.yandex import YandexOAuthClient
from app.modules.settings import OAuthSettingsDto


def _get_cabinet_only_client(
    provider: OAuthProvider, settings: OAuthSettingsDto
) -> Optional[OAuthProviderClient]:
    if provider is OAuthProvider.GOOGLE:
        if not settings.is_google_configured:
            raise AuthenticationError(
                "Google OAuth is not configured", code=ErrorCode.OAUTH_PROVIDER_NOT_CONFIGURED
            )
        assert settings.google_client_id is not None
        assert settings.google_client_secret is not None
        return GoogleOAuthClient(
            settings.google_client_id, settings.google_client_secret.get_secret_value()
        )

    if provider is OAuthProvider.YANDEX:
        if not settings.is_yandex_configured:
            raise AuthenticationError(
                "Yandex OAuth is not configured", code=ErrorCode.OAUTH_PROVIDER_NOT_CONFIGURED
            )
        assert settings.yandex_client_id is not None
        assert settings.yandex_client_secret is not None
        return YandexOAuthClient(
            settings.yandex_client_id, settings.yandex_client_secret.get_secret_value()
        )

    return None


def _require_usable(label: str, configured: bool, enabled: bool, require_enabled: bool) -> None:
    if not configured:
        raise AuthenticationError(
            f"{label} is not configured", code=ErrorCode.OAUTH_PROVIDER_NOT_CONFIGURED
        )
    if require_enabled and not enabled:
        raise AuthenticationError(f"{label} is disabled", code=ErrorCode.OAUTH_PROVIDER_DISABLED)


def get_oauth_client(
    provider: OAuthProvider, settings: OAuthSettingsDto, *, require_enabled: bool = True
) -> OAuthProviderClient:
    if provider is OAuthProvider.GITHUB:
        _require_usable(
            "GitHub OAuth", settings.is_github_configured, settings.github_enabled, require_enabled
        )
        assert settings.github_client_id is not None
        assert settings.github_client_secret is not None
        return GitHubOAuthClient(
            settings.github_client_id, settings.github_client_secret.get_secret_value()
        )

    if provider is OAuthProvider.TELEGRAM:
        _require_usable(
            "Telegram OAuth",
            settings.is_telegram_configured,
            settings.telegram_enabled,
            require_enabled,
        )
        assert settings.telegram_client_id is not None
        assert settings.telegram_client_secret is not None
        return TelegramOAuthClient(
            settings.telegram_client_id, settings.telegram_client_secret.get_secret_value()
        )

    if provider is OAuthProvider.OIDC:
        _require_usable("OIDC", settings.is_oidc_configured, settings.oidc_enabled, require_enabled)
        assert settings.oidc_issuer_url is not None
        assert settings.oidc_client_id is not None
        assert settings.oidc_client_secret is not None
        return OIDCOAuthClient(
            settings.oidc_issuer_url,
            settings.oidc_client_id,
            settings.oidc_client_secret.get_secret_value(),
        )

    cabinet_client = _get_cabinet_only_client(provider, settings)
    if cabinet_client is not None:
        return cabinet_client

    raise AuthenticationError(
        f"Unsupported OAuth provider: {provider}", code=ErrorCode.OAUTH_PROVIDER_UNSUPPORTED
    )

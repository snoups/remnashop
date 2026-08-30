from app.core.enums import OAuthProvider
from app.core.exceptions import AuthenticationError
from app.modules.auth.oauth.base import OAuthProviderClient
from app.modules.auth.oauth.github import GitHubOAuthClient
from app.modules.auth.oauth.oidc import OIDCOAuthClient
from app.modules.auth.oauth.telegram import TelegramOAuthClient
from app.modules.settings import OAuthSettingsDto


def get_oauth_client(provider: OAuthProvider, settings: OAuthSettingsDto) -> OAuthProviderClient:
    if provider is OAuthProvider.GITHUB:
        if not settings.is_github_configured:
            raise AuthenticationError("GitHub OAuth is not configured")
        if not settings.github_enabled:
            raise AuthenticationError("GitHub OAuth is disabled")
        assert settings.github_client_id is not None
        assert settings.github_client_secret is not None
        return GitHubOAuthClient(settings.github_client_id, settings.github_client_secret)

    if provider is OAuthProvider.TELEGRAM:
        if not settings.is_telegram_configured:
            raise AuthenticationError("Telegram OAuth is not configured")
        if not settings.telegram_enabled:
            raise AuthenticationError("Telegram OAuth is disabled")
        assert settings.telegram_client_id is not None
        assert settings.telegram_client_secret is not None
        return TelegramOAuthClient(settings.telegram_client_id, settings.telegram_client_secret)

    if provider is OAuthProvider.OIDC:
        if not settings.is_oidc_configured:
            raise AuthenticationError("OIDC is not configured")
        if not settings.oidc_enabled:
            raise AuthenticationError("OIDC is disabled")
        assert settings.oidc_issuer_url is not None
        assert settings.oidc_client_id is not None
        assert settings.oidc_client_secret is not None
        return OIDCOAuthClient(
            settings.oidc_issuer_url, settings.oidc_client_id, settings.oidc_client_secret
        )

    raise AuthenticationError(f"Unsupported OAuth provider: {provider}")

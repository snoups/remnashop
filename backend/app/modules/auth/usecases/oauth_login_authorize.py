from authlib.common.security import generate_token

from app.core.config import AppConfig
from app.core.enums import OAuthProvider
from app.core.exceptions import AuthenticationError
from app.modules.auth.oauth.base import OAUTH_EXCHANGE_ERRORS, build_redirect_uri
from app.modules.auth.oauth.registry import get_oauth_client
from app.modules.auth.oauth.state_store import OAuthFlowPurpose, OAuthStateStore
from app.modules.settings import SettingsRepository


class OAuthLoginAuthorizeUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        state_store: OAuthStateStore,
        config: AppConfig,
    ) -> None:
        self._settings_repository = settings_repository
        self._state_store = state_store
        self._config = config

    async def execute(self, provider: OAuthProvider) -> str:
        settings = await self._settings_repository.get_oauth_settings()
        client = get_oauth_client(provider, settings)

        code_verifier = generate_token(48) if client.requires_pkce else None
        state = await self._state_store.create(
            provider=provider,
            purpose=OAuthFlowPurpose.LOGIN,
            user_id=None,
            code_verifier=code_verifier,
        )
        redirect_uri = build_redirect_uri(self._config.domain.get_secret_value(), provider)
        try:
            return await client.authorization_url(redirect_uri, state, code_verifier)
        except OAUTH_EXCHANGE_ERRORS as error:
            raise AuthenticationError("Failed to reach OAuth provider") from error

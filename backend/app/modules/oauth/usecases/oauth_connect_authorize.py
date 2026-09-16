from authlib.common.security import generate_token

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.exceptions import AuthenticationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.oauth.providers.base import OAUTH_EXCHANGE_ERRORS, build_redirect_uri
from app.modules.oauth.providers.registry import get_oauth_client
from app.modules.oauth.providers.state_store import OAuthFlowPurpose, OAuthStateStore
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class OAuthConnectAuthorizeUseCase(UseCase[OAuthProvider, str]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        state_store: OAuthStateStore,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._state_store = state_store
        self._config = config
        self._uow = uow

    async def _execute(self, actor: UserDto, data: OAuthProvider) -> str:
        async with self._uow:
            settings = await self._settings_repository.get_oauth_settings()
            client = get_oauth_client(data, settings)

            code_verifier = generate_token(48) if client.requires_pkce else None
        state = await self._state_store.create(
            provider=data,
            purpose=OAuthFlowPurpose.CONNECT,
            user_id=actor.id,
            code_verifier=code_verifier,
        )
        redirect_uri = build_redirect_uri(self._config.domain.get_secret_value(), data)
        try:
            return await client.authorization_url(redirect_uri, state, code_verifier)
        except OAUTH_EXCHANGE_ERRORS as error:
            raise AuthenticationError("Failed to reach OAuth provider") from error

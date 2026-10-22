from typing import Final, Optional

from authlib.common.security import generate_token

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.cabinet_auth.dto import InviteCodesDto
from app.modules.oauth import (
    OAUTH_EXCHANGE_ERRORS,
    OAuthFlowPurpose,
    OAuthStateStore,
    build_cabinet_redirect_uri,
    get_oauth_client,
    new_binding,
)
from app.modules.settings import SettingsRepository

CABINET_OAUTH_PROVIDERS: Final[frozenset[OAuthProvider]] = frozenset(
    {OAuthProvider.TELEGRAM, OAuthProvider.GOOGLE, OAuthProvider.YANDEX}
)


class CabinetOAuthAuthorizeUseCase:
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

    async def execute(
        self, provider: OAuthProvider, codes: InviteCodesDto, link_user_id: Optional[int] = None
    ) -> tuple[str, str]:
        # with link_user_id the round trip links the provider to that customer instead of signing in
        if provider not in CABINET_OAUTH_PROVIDERS:
            raise AuthenticationError(
                "Provider is not available for cabinet sign-in",
                code=ErrorCode.OAUTH_PROVIDER_UNSUPPORTED,
            )
        cabinet_url = self._config.cabinet.url
        if not cabinet_url:
            raise AuthenticationError(
                "The cabinet URL is not configured", code=ErrorCode.OAUTH_PROVIDER_NOT_CONFIGURED
            )
        async with self._uow:
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            if not cabinet.is_oauth_enabled(provider):
                raise AuthenticationError(
                    "Provider is disabled", code=ErrorCode.OAUTH_PROVIDER_DISABLED
                )
            settings = await self._settings_repository.get_oauth_settings()
            client = get_oauth_client(provider, settings, require_enabled=False)

        code_verifier = generate_token(48) if client.requires_pkce else None
        binding, binding_hash = new_binding()
        state = await self._state_store.create(
            provider=provider,
            purpose=(
                OAuthFlowPurpose.CABINET_LOGIN
                if link_user_id is None
                else OAuthFlowPurpose.CABINET_CONNECT
            ),
            user_id=link_user_id,
            code_verifier=code_verifier,
            binding_hash=binding_hash,
            referral_code=codes.referral_code,
            ad_link_code=codes.ad_link_code,
        )
        redirect_uri = build_cabinet_redirect_uri(cabinet_url, provider)
        try:
            url = await client.authorization_url(redirect_uri, state, code_verifier)
        except OAUTH_EXCHANGE_ERRORS as error:
            raise AuthenticationError(
                "Failed to reach OAuth provider", code=ErrorCode.OAUTH_PROVIDER_UNREACHABLE
            ) from error
        return url, binding

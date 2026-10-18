from typing import Optional

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.auth import IssuedSession
from app.modules.cabinet_auth.dto import InviteCodesDto
from app.modules.cabinet_auth.sign_in import CabinetSignIn
from app.modules.oauth import (
    OAUTH_EXCHANGE_ERRORS,
    OAuthFlowPurpose,
    OAuthProfile,
    OAuthStateStore,
    binding_matches,
    build_cabinet_redirect_uri,
    get_oauth_client,
)
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class CabinetOAuthCallbackUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        state_store: OAuthStateStore,
        sign_in: CabinetSignIn,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._state_store = state_store
        self._sign_in = sign_in
        self._config = config
        self._uow = uow

    async def execute(
        self,
        provider: OAuthProvider,
        code: str,
        state: str,
        binding: Optional[str],
        client_ip: str,
        user_agent: Optional[str],
    ) -> tuple[UserDto, IssuedSession]:
        profile, codes = await self._fetch(provider, code, state, binding, link_user_id=None)
        return await self._sign_in.oauth(provider, profile, codes, client_ip, user_agent)

    async def fetch_profile(
        self,
        provider: OAuthProvider,
        code: str,
        state: str,
        binding: Optional[str],
        *,
        link_user_id: Optional[int],
    ) -> OAuthProfile:
        profile, _ = await self._fetch(provider, code, state, binding, link_user_id=link_user_id)
        return profile

    async def _fetch(
        self,
        provider: OAuthProvider,
        code: str,
        state: str,
        binding: Optional[str],
        *,
        link_user_id: Optional[int],
    ) -> tuple[OAuthProfile, InviteCodesDto]:
        # a sign-in state never links and a link state never signs in
        purpose = (
            OAuthFlowPurpose.CABINET_LOGIN
            if link_user_id is None
            else OAuthFlowPurpose.CABINET_CONNECT
        )
        state_data = await self._state_store.consume(state)
        if (
            state_data is None
            or state_data.purpose is not purpose
            or state_data.user_id != link_user_id
            or state_data.provider is not provider
            or not binding_matches(binding, state_data.binding_hash)
        ):
            raise AuthenticationError(
                "Invalid or expired OAuth state", code=ErrorCode.OAUTH_STATE_INVALID
            )

        cabinet_url = self._config.cabinet.url
        if not cabinet_url:
            raise AuthenticationError(
                "The cabinet URL is not configured", code=ErrorCode.OAUTH_PROVIDER_NOT_CONFIGURED
            )
        async with self._uow:
            cabinet = await self._settings_repository.get_cabinet_auth_settings()
            if not getattr(cabinet, f"{provider.value.lower()}_enabled"):
                raise AuthenticationError(
                    "Provider is disabled", code=ErrorCode.OAUTH_PROVIDER_DISABLED
                )
            settings = await self._settings_repository.get_oauth_settings()
            client = get_oauth_client(provider, settings, require_enabled=False)
        redirect_uri = build_cabinet_redirect_uri(cabinet_url, provider)
        try:
            profile = await client.fetch_identity(redirect_uri, code, state_data.code_verifier)
        except OAUTH_EXCHANGE_ERRORS as error:
            raise AuthenticationError(
                "Failed to exchange OAuth code", code=ErrorCode.OAUTH_CODE_EXCHANGE_FAILED
            ) from error
        return profile, InviteCodesDto(
            referral_code=state_data.referral_code, ad_link_code=state_data.ad_link_code
        )

from typing import Optional

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.ports import EventPublisher
from app.modules.auth import IssuedSession, SessionIssuer
from app.modules.oauth.events import OAuthLoginFailedEvent, OAuthLoginSucceededEvent
from app.modules.oauth.providers.base import OAUTH_EXCHANGE_ERRORS, build_redirect_uri
from app.modules.oauth.providers.registry import get_oauth_client
from app.modules.oauth.providers.state_store import OAuthFlowPurpose, OAuthStateStore
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto, UserRepository


class OAuthLoginCallbackUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        state_store: OAuthStateStore,
        oauth_identity_repository: OAuthIdentityRepository,
        user_repository: UserRepository,
        config: AppConfig,
        event_publisher: EventPublisher,
        session_issuer: SessionIssuer,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._state_store = state_store
        self._oauth_identity_repository = oauth_identity_repository
        self._user_repository = user_repository
        self._config = config
        self._event_publisher = event_publisher
        self._session_issuer = session_issuer
        self._uow = uow

    async def execute(
        self,
        provider: OAuthProvider,
        code: str,
        state: str,
        client_ip: str,
        user_agent: Optional[str],
    ) -> tuple[UserDto, IssuedSession]:
        state_data = await self._state_store.consume(state)

        if (
            state_data is None
            or state_data.purpose != OAuthFlowPurpose.LOGIN
            or state_data.provider != provider
        ):
            async with self._uow:
                await self._event_publisher.publish(
                    OAuthLoginFailedEvent(provider=provider, ip_address=client_ip)
                )
            raise AuthenticationError(
                "Invalid or expired OAuth state", code=ErrorCode.OAUTH_STATE_INVALID
            )

        async with self._uow:
            settings = await self._settings_repository.get_oauth_settings()
            client = get_oauth_client(provider, settings)
            redirect_uri = build_redirect_uri(self._config.domain.get_secret_value(), provider)
        try:
            profile = await client.fetch_identity(redirect_uri, code, state_data.code_verifier)
        except OAUTH_EXCHANGE_ERRORS as error:
            async with self._uow:
                await self._event_publisher.publish(
                    OAuthLoginFailedEvent(provider=provider, ip_address=client_ip)
                )
            raise AuthenticationError(
                "Failed to exchange OAuth code", code=ErrorCode.OAUTH_CODE_EXCHANGE_FAILED
            ) from error

        external_id = profile.external_id
        user: Optional[UserDto] = None
        if provider is OAuthProvider.TELEGRAM:
            async with self._uow:
                user = await self._user_repository.get_by_telegram_id(int(external_id))
        else:
            async with self._uow:
                replaced = False
                if provider is OAuthProvider.OIDC:
                    current = await self._settings_repository.lock_oauth_settings(exclusive=False)
                    # the sub was fetched from an issuer that is no longer configured
                    replaced = current.oidc_issuer_url != settings.oidc_issuer_url
                identity = (
                    None
                    if replaced
                    else await self._oauth_identity_repository.get_by_provider_external_id(
                        provider, external_id
                    )
                )
                if identity is not None:
                    user = await self._user_repository.find_by_id(identity.user_id)
        # one message for a missing, blocked or non-staff user, so an
        # unauthenticated caller can't learn blocked-status (as in LoginUseCase)
        if user is None or user.is_blocked or not user.is_privileged:
            async with self._uow:
                await self._event_publisher.publish(
                    OAuthLoginFailedEvent(provider=provider, ip_address=client_ip)
                )
            raise AuthenticationError(
                "This account is not linked to any user", code=ErrorCode.OAUTH_ACCOUNT_NOT_LINKED
            )

        issued = await self._session_issuer.issue(user.id, client_ip, user_agent)
        async with self._uow:
            await self._event_publisher.publish(
                OAuthLoginSucceededEvent(user=user, provider=provider, ip_address=client_ip)
            )
        return user, issued

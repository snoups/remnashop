from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.oauth.dto import CreateOAuthIdentityDto, OAuthCallbackDto, OAuthIdentityDto
from app.modules.oauth.events import OAuthIdentityConnectedEvent
from app.modules.oauth.providers.base import OAUTH_EXCHANGE_ERRORS, build_redirect_uri
from app.modules.oauth.providers.registry import get_oauth_client
from app.modules.oauth.providers.state_store import OAuthFlowPurpose, OAuthStateStore
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto, UserRepository


class OAuthConnectCallbackUseCase(UseCase[OAuthCallbackDto, OAuthIdentityDto, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        state_store: OAuthStateStore,
        oauth_identity_repository: OAuthIdentityRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
        config: AppConfig,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._state_store = state_store
        self._oauth_identity_repository = oauth_identity_repository
        self._user_repository = user_repository
        self._uow = uow
        self._config = config
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: OAuthCallbackDto) -> OAuthIdentityDto:
        state_data = await self._state_store.consume(data.state)

        async with self._uow:
            if (
                state_data is None
                or state_data.purpose != OAuthFlowPurpose.CONNECT
                or state_data.provider != data.provider
                or state_data.user_id != actor.id
            ):
                raise AuthenticationError(
                    "Invalid or expired OAuth state", code=ErrorCode.OAUTH_STATE_INVALID
                )

            settings = await self._settings_repository.get_oauth_settings()
            client = get_oauth_client(data.provider, settings)
            redirect_uri = build_redirect_uri(self._config.domain.get_secret_value(), data.provider)
        try:
            profile = await client.fetch_identity(
                redirect_uri,
                data.code,
                state_data.code_verifier,
            )
        except OAUTH_EXCHANGE_ERRORS as error:
            raise AuthenticationError(
                "Failed to exchange OAuth code", code=ErrorCode.OAUTH_CODE_EXCHANGE_FAILED
            ) from error

        external_id = profile.external_id
        external_login = profile.login
        if data.provider is OAuthProvider.TELEGRAM:
            async with self._uow:
                updated = await self._user_repository.set_telegram_id(actor.id, int(external_id))
                await self._event_publisher.publish(
                    OAuthIdentityConnectedEvent(
                        user=actor, provider=data.provider, ip_address=data.client_ip
                    )
                )
            return OAuthIdentityDto(
                user_id=updated.id,
                provider=OAuthProvider.TELEGRAM,
                external_id=external_id,
                external_login=external_login,
            )

        async with self._uow:
            existing = await self._oauth_identity_repository.get_by_provider_external_id(
                data.provider, external_id
            )
            if existing is not None and existing.user_id != actor.id:
                raise ConflictError(
                    "This account is already linked to another user",
                    code=ErrorCode.OAUTH_ACCOUNT_LINKED_ELSEWHERE,
                )

        async with self._uow:
            if data.provider is OAuthProvider.OIDC:
                current = await self._settings_repository.lock_oauth_settings(exclusive=False)
                # the identity was fetched from an issuer that is no longer configured
                if current.oidc_issuer_url != settings.oidc_issuer_url:
                    raise AuthenticationError(
                        "OAuth settings changed during sign-in", code=ErrorCode.OAUTH_STATE_INVALID
                    )
            identity = await self._oauth_identity_repository.create(
                CreateOAuthIdentityDto(
                    user_id=actor.id,
                    provider=data.provider,
                    external_id=external_id,
                    external_login=external_login,
                )
            )
            await self._event_publisher.publish(
                OAuthIdentityConnectedEvent(
                    user=actor,
                    provider=data.provider,
                    ip_address=data.client_ip,
                )
            )
        return identity

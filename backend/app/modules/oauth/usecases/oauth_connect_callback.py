from dataclasses import dataclass

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.oauth.dto import CreateOAuthIdentityDto, OAuthIdentityDto
from app.modules.oauth.events import OAuthIdentityConnectedEvent
from app.modules.oauth.providers.base import OAUTH_EXCHANGE_ERRORS, build_redirect_uri
from app.modules.oauth.providers.registry import get_oauth_client
from app.modules.oauth.providers.state_store import OAuthFlowPurpose, OAuthStateStore
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class OAuthCallbackDto:
    provider: OAuthProvider
    code: str
    state: str
    client_ip: str


class OAuthConnectCallbackUseCase(UseCase[OAuthCallbackDto, OAuthIdentityDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        state_store: OAuthStateStore,
        oauth_identity_repository: OAuthIdentityRepository,
        uow: UnitOfWork,
        config: AppConfig,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._state_store = state_store
        self._oauth_identity_repository = oauth_identity_repository
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
                raise AuthenticationError("Invalid or expired OAuth state")

            settings = await self._settings_repository.get_oauth_settings()
            client = get_oauth_client(data.provider, settings)
            redirect_uri = build_redirect_uri(self._config.domain.get_secret_value(), data.provider)
        try:
            external_id, external_login = await client.fetch_identity(
                redirect_uri,
                data.code,
                state_data.code_verifier,
            )
        except OAUTH_EXCHANGE_ERRORS as error:
            raise AuthenticationError("Failed to exchange OAuth code") from error

        async with self._uow:
            existing = await self._oauth_identity_repository.get_by_provider_external_id(
                data.provider, external_id
            )
            if existing is not None and existing.user_id != actor.id:
                raise ConflictError("This account is already linked to another user")

        async with self._uow:
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

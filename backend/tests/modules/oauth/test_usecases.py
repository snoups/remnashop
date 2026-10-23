import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, OAuthProvider, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError, ConflictError, PermissionDeniedError
from app.core.ports import EventPublisher
from app.modules.auth import BootstrapOwnerUseCase, SessionIssuer, SessionRepository
from app.modules.blacklist import BlacklistRepository
from app.modules.oauth.dto import CreateOAuthIdentityDto, OAuthCallbackDto, OAuthDisconnectDto
from app.modules.oauth.events import OAuthLoginFailedEvent
from app.modules.oauth.providers.base import OAuthProfile
from app.modules.oauth.providers.oidc import OIDCOAuthClient
from app.modules.oauth.providers.registry import get_oauth_client
from app.modules.oauth.providers.state_store import (
    OAuthFlowPurpose,
    OAuthStateStore,
    new_binding,
)
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.oauth.usecases import (
    ListOAuthIdentitiesUseCase,
    OAuthConnectAuthorizeUseCase,
    OAuthConnectCallbackUseCase,
    OAuthDisconnectUseCase,
    OAuthLoginAuthorizeUseCase,
    OAuthLoginCallbackUseCase,
    oauth_connect_callback,
    oauth_login_callback,
)
from app.modules.settings import SettingsRepository, UpdateOAuthSettingsDto
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

PASSWORD = "Sup3rSecretPassw0rd1234567890"
CLIENT_IP = "203.0.113.1"
REGULAR_USER = UserDto(id=999, name="Bob", role=Role.USER, language=Locale.EN)
USER_AGENT = "pytest"


async def _newest_outbox_row(session: AsyncSession, event_type: str) -> EventOutboxEntry:
    rows = (
        await session.scalars(
            select(EventOutboxEntry)
            .where(EventOutboxEntry.event_type == event_type)
            .order_by(EventOutboxEntry.id)
        )
    ).all()
    assert rows, f"no outbox row for '{event_type}'"
    return rows[-1]


def _bootstrap_use_case(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
) -> BootstrapOwnerUseCase:
    return BootstrapOwnerUseCase(
        user_repository,
        uow,
        config,
        event_publisher,
        SessionIssuer(session_repository, uow, config),
    )


def _oauth_login_callback_use_case(
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
) -> OAuthLoginCallbackUseCase:
    return OAuthLoginCallbackUseCase(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        config,
        event_publisher,
        SessionIssuer(session_repository, uow, config),
        uow,
    )


async def _bootstrap_owner(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
) -> UserDto:
    owner, _ = await _bootstrap_use_case(
        user_repository, uow, config, event_publisher, session_repository
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)
    return owner


class _StubOAuthClient:
    requires_pkce = False

    async def authorization_url(self, redirect_uri: str, state: str, code_verifier: object) -> str:
        return f"https://example.com/authorize?state={state}"

    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: object
    ) -> OAuthProfile:
        return OAuthProfile(external_id="external-123", login="octocat")


class _FailingOAuthClient(_StubOAuthClient):
    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: object
    ) -> OAuthProfile:
        raise KeyError("id")


async def test_oauth_login_authorize_returns_url_for_configured_provider(
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    config: AppConfig,
    uow: UnitOfWork,
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            github_client_id="gh-id",
            github_client_secret="gh-secret",
            github_enabled=True,
            telegram_client_id=None,
            telegram_client_secret=None,
        )
    )
    use_case = OAuthLoginAuthorizeUseCase(settings_repository, oauth_state_store, config, uow)

    url, binding = await use_case.execute(OAuthProvider.GITHUB)

    assert url.startswith("https://github.com/login/oauth/authorize")
    assert "state=" in url
    assert binding


async def test_oauth_login_authorize_rejects_unconfigured_provider(
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    config: AppConfig,
    uow: UnitOfWork,
) -> None:
    use_case = OAuthLoginAuthorizeUseCase(settings_repository, oauth_state_store, config, uow)

    with pytest.raises(AuthenticationError):
        await use_case.execute(OAuthProvider.GITHUB)


async def test_oauth_login_callback_rejects_unknown_state(
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
) -> None:
    use_case = _oauth_login_callback_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        event_publisher,
        session_repository,
    )

    with pytest.raises(AuthenticationError):
        await use_case.execute(
            OAuthProvider.GITHUB,
            code="code",
            state="unknown-state",
            binding=None,
            client_ip=CLIENT_IP,
            user_agent=USER_AGENT,
        )


async def test_oauth_login_callback_rejects_state_from_connect_flow(
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
) -> None:
    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.CONNECT,
        user_id=1,
        code_verifier=None,
    )
    use_case = _oauth_login_callback_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        event_publisher,
        session_repository,
    )

    with pytest.raises(AuthenticationError):
        await use_case.execute(
            OAuthProvider.GITHUB,
            code="code",
            state=state,
            binding=None,
            client_ip=CLIENT_IP,
            user_agent=USER_AGENT,
        )


async def test_oauth_login_callback_rejects_unlinked_identity(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
) -> None:
    monkeypatch.setattr(
        oauth_login_callback, "get_oauth_client", lambda provider, settings: _StubOAuthClient()
    )
    binding, binding_hash = new_binding()
    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
        binding_hash=binding_hash,
    )
    use_case = _oauth_login_callback_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        event_publisher,
        session_repository,
    )

    with pytest.raises(AuthenticationError):
        await use_case.execute(
            OAuthProvider.GITHUB,
            code="code",
            state=state,
            binding=binding,
            client_ip=CLIENT_IP,
            user_agent=USER_AGENT,
        )


async def test_oauth_login_callback_reports_provider_exchange_failure(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    session_repository: SessionRepository,
    session: AsyncSession,
    event_publisher: EventPublisher,
) -> None:
    monkeypatch.setattr(
        oauth_login_callback, "get_oauth_client", lambda provider, settings: _FailingOAuthClient()
    )

    binding, binding_hash = new_binding()
    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
        binding_hash=binding_hash,
    )
    use_case = _oauth_login_callback_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        event_publisher,
        session_repository,
    )

    with pytest.raises(AuthenticationError):
        await use_case.execute(
            OAuthProvider.GITHUB,
            code="code",
            state=state,
            binding=binding,
            client_ip=CLIENT_IP,
            user_agent=USER_AGENT,
        )

    row = await _newest_outbox_row(session, OAuthLoginFailedEvent.__name__)
    assert row.payload["provider"] == OAuthProvider.GITHUB


async def test_oauth_login_callback_succeeds_for_linked_identity(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
) -> None:
    monkeypatch.setattr(
        oauth_login_callback, "get_oauth_client", lambda provider, settings: _StubOAuthClient()
    )
    owner, _ = await _bootstrap_use_case(
        user_repository, uow, config, event_publisher, session_repository
    ).execute(
        login="admin",
        password=PASSWORD,
        client_ip=CLIENT_IP,
        user_agent=USER_AGENT,
    )
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=owner.id,
            provider=OAuthProvider.GITHUB,
            external_id="external-123",
            external_login=None,
        )
    )
    binding, binding_hash = new_binding()
    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
        binding_hash=binding_hash,
    )
    use_case = _oauth_login_callback_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        event_publisher,
        session_repository,
    )

    logged_in_user, issued = await use_case.execute(
        OAuthProvider.GITHUB,
        code="code",
        state=state,
        binding=binding,
        client_ip=CLIENT_IP,
        user_agent=USER_AGENT,
    )

    assert logged_in_user.id == owner.id
    assert issued.access_token


async def test_regular_user_cannot_connect_authorize(
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    config: AppConfig,
    uow: UnitOfWork,
) -> None:
    interactor = OAuthConnectAuthorizeUseCase(settings_repository, oauth_state_store, config, uow)

    with pytest.raises(PermissionDeniedError):
        await interactor(REGULAR_USER, OAuthProvider.GITHUB)


async def test_connect_authorize_returns_url(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    session_repository: SessionRepository,
) -> None:
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            github_client_id="gh-id",
            github_client_secret="gh-secret",
            github_enabled=True,
            telegram_client_id=None,
            telegram_client_secret=None,
        )
    )
    interactor = OAuthConnectAuthorizeUseCase(settings_repository, oauth_state_store, config, uow)

    url = await interactor(owner, OAuthProvider.GITHUB)

    assert url.startswith("https://github.com/login/oauth/authorize")


async def test_connect_callback_links_identity_to_actor(
    monkeypatch: pytest.MonkeyPatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    session_repository: SessionRepository,
) -> None:
    monkeypatch.setattr(
        oauth_connect_callback, "get_oauth_client", lambda provider, settings: _StubOAuthClient()
    )
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.CONNECT,
        user_id=owner.id,
        code_verifier=None,
    )
    interactor = OAuthConnectCallbackUseCase(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        BlacklistRepository(user_repository.session),
        uow,
        config,
        event_publisher,
    )

    identity = await interactor(
        owner,
        OAuthCallbackDto(
            provider=OAuthProvider.GITHUB, code="code", state=state, client_ip=CLIENT_IP
        ),
    )

    assert identity.external_id == "external-123"
    assert identity.external_login == "octocat"
    assert identity.user_id == owner.id


async def test_connect_callback_reports_provider_exchange_failure(
    monkeypatch: pytest.MonkeyPatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    session_repository: SessionRepository,
) -> None:
    monkeypatch.setattr(
        oauth_connect_callback, "get_oauth_client", lambda provider, settings: _FailingOAuthClient()
    )
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.CONNECT,
        user_id=owner.id,
        code_verifier=None,
    )
    interactor = OAuthConnectCallbackUseCase(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        BlacklistRepository(user_repository.session),
        uow,
        config,
        event_publisher,
    )

    with pytest.raises(AuthenticationError):
        await interactor(
            owner,
            OAuthCallbackDto(
                provider=OAuthProvider.GITHUB, code="code", state=state, client_ip=CLIENT_IP
            ),
        )

    assert await oauth_identity_repository.list_by_user(owner.id) == []


async def test_connect_callback_rejects_state_bound_to_different_actor(
    monkeypatch: pytest.MonkeyPatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    session_repository: SessionRepository,
) -> None:
    monkeypatch.setattr(
        oauth_connect_callback, "get_oauth_client", lambda provider, settings: _StubOAuthClient()
    )
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.CONNECT,
        user_id=owner.id + 1,
        code_verifier=None,
    )
    interactor = OAuthConnectCallbackUseCase(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        BlacklistRepository(user_repository.session),
        uow,
        config,
        event_publisher,
    )

    with pytest.raises(AuthenticationError):
        await interactor(
            owner,
            OAuthCallbackDto(
                provider=OAuthProvider.GITHUB, code="code", state=state, client_ip=CLIENT_IP
            ),
        )


async def test_connect_callback_rejects_identity_already_linked_to_another_user(
    monkeypatch: pytest.MonkeyPatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    session_repository: SessionRepository,
) -> None:
    monkeypatch.setattr(
        oauth_connect_callback, "get_oauth_client", lambda provider, settings: _StubOAuthClient()
    )
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )

    async with uow:
        other_user = await user_repository.create(
            CreateUserDto(login="other", name="other", role=Role.ADMIN, language=Locale.EN)
        )
        await uow.commit()

    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=other_user.id,
            provider=OAuthProvider.GITHUB,
            external_id="external-123",
            external_login=None,
        )
    )

    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.CONNECT,
        user_id=owner.id,
        code_verifier=None,
    )
    interactor = OAuthConnectCallbackUseCase(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        BlacklistRepository(user_repository.session),
        uow,
        config,
        event_publisher,
    )

    with pytest.raises(ConflictError):
        await interactor(
            owner,
            OAuthCallbackDto(
                provider=OAuthProvider.GITHUB, code="code", state=state, client_ip=CLIENT_IP
            ),
        )


async def test_disconnect_removes_identity(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    oauth_identity_repository: OAuthIdentityRepository,
    session_repository: SessionRepository,
) -> None:
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=owner.id,
            provider=OAuthProvider.GITHUB,
            external_id="external-123",
            external_login=None,
        )
    )
    interactor = OAuthDisconnectUseCase(
        oauth_identity_repository, user_repository, uow, event_publisher
    )

    await interactor(owner, OAuthDisconnectDto(provider=OAuthProvider.GITHUB, client_ip=CLIENT_IP))

    identities = await oauth_identity_repository.list_by_user(owner.id)
    assert identities == []


async def test_disconnect_is_idempotent_when_nothing_linked(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    oauth_identity_repository: OAuthIdentityRepository,
    session_repository: SessionRepository,
) -> None:
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    interactor = OAuthDisconnectUseCase(
        oauth_identity_repository, user_repository, uow, event_publisher
    )

    await interactor(owner, OAuthDisconnectDto(provider=OAuthProvider.GITHUB, client_ip=CLIENT_IP))


async def test_list_returns_only_actors_own_identities(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    oauth_identity_repository: OAuthIdentityRepository,
    session_repository: SessionRepository,
) -> None:
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    async with uow:
        other_user = await user_repository.create(
            CreateUserDto(login="other", name="other", role=Role.ADMIN, language=Locale.EN)
        )
        await uow.commit()

    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=owner.id,
            provider=OAuthProvider.GITHUB,
            external_id="owner-id",
            external_login=None,
        )
    )
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=other_user.id,
            provider=OAuthProvider.GITHUB,
            external_id="other-id",
            external_login=None,
        )
    )

    interactor = ListOAuthIdentitiesUseCase(oauth_identity_repository, uow)
    identities = await interactor(owner)

    assert len(identities) == 1
    assert identities[0].external_id == "owner-id"


async def test_registry_rejects_unconfigured_oidc(
    settings_repository: SettingsRepository,
) -> None:
    settings = await settings_repository.get_oauth_settings()

    with pytest.raises(AuthenticationError):
        get_oauth_client(OAuthProvider.OIDC, settings)


async def test_registry_rejects_disabled_oidc(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            oidc_issuer_url="https://keycloak.example.com/realms/myrealm",
            oidc_client_id="oidc-id",
            oidc_client_secret="oidc-secret",
            oidc_display_name="Keycloak",
        )
    )
    settings = await settings_repository.get_oauth_settings()

    with pytest.raises(AuthenticationError):
        get_oauth_client(OAuthProvider.OIDC, settings)


async def test_registry_returns_oidc_client_when_configured_and_enabled(
    settings_repository: SettingsRepository,
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            oidc_issuer_url="https://keycloak.example.com/realms/myrealm",
            oidc_client_id="oidc-id",
            oidc_client_secret="oidc-secret",
            oidc_display_name="Keycloak",
            oidc_enabled=True,
        )
    )
    settings = await settings_repository.get_oauth_settings()

    client = get_oauth_client(OAuthProvider.OIDC, settings)

    assert isinstance(client, OIDCOAuthClient)
    assert client.requires_pkce


class _IssuerSwappingClient(_StubOAuthClient):
    """The OIDC issuer is changed while the code exchange is in flight."""

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self.after_swap: list[object] = []

    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: object
    ) -> OAuthProfile:
        async with self._uow:
            await self._settings_repository.update_oauth_settings(
                UpdateOAuthSettingsDto(oidc_issuer_url="https://issuer-b.example")
            )
        for hook in self.after_swap:
            await hook()  # type: ignore[operator]
        return OAuthProfile(external_id="external-123", login="octocat")


async def _with_issuer(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_oauth_settings(
            UpdateOAuthSettingsDto(oidc_issuer_url="https://issuer-a.example")
        )


async def test_connect_callback_refuses_an_identity_from_a_replaced_oidc_issuer(
    monkeypatch: pytest.MonkeyPatch,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    session_repository: SessionRepository,
) -> None:
    await _with_issuer(settings_repository, uow)
    client = _IssuerSwappingClient(settings_repository, uow)
    monkeypatch.setattr(
        oauth_connect_callback, "get_oauth_client", lambda provider, settings: client
    )
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    state = await oauth_state_store.create(
        provider=OAuthProvider.OIDC,
        purpose=OAuthFlowPurpose.CONNECT,
        user_id=owner.id,
        code_verifier=None,
    )
    interactor = OAuthConnectCallbackUseCase(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        BlacklistRepository(user_repository.session),
        uow,
        config,
        event_publisher,
    )

    with pytest.raises(AuthenticationError) as error:
        await interactor(
            owner,
            OAuthCallbackDto(
                provider=OAuthProvider.OIDC, code="code", state=state, client_ip=CLIENT_IP
            ),
        )

    assert error.value.code is ErrorCode.OAUTH_STATE_INVALID
    assert await oauth_identity_repository.list_by_user(owner.id) == []


async def test_login_callback_refuses_a_sub_fetched_from_a_replaced_oidc_issuer(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
) -> None:
    await _with_issuer(settings_repository, uow)
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    client = _IssuerSwappingClient(settings_repository, uow)

    async def _new_issuer_links_the_same_sub() -> None:
        async with uow:
            await oauth_identity_repository.create(
                CreateOAuthIdentityDto(
                    user_id=owner.id,
                    provider=OAuthProvider.OIDC,
                    external_id="external-123",
                    external_login="octocat",
                )
            )

    client.after_swap.append(_new_issuer_links_the_same_sub)
    monkeypatch.setattr(oauth_login_callback, "get_oauth_client", lambda *_: client)
    binding, binding_hash = new_binding()
    state = await oauth_state_store.create(
        provider=OAuthProvider.OIDC,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
        binding_hash=binding_hash,
    )
    use_case = _oauth_login_callback_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        event_publisher,
        session_repository,
    )

    with pytest.raises(AuthenticationError):
        await use_case.execute(
            OAuthProvider.OIDC,
            code="code",
            state=state,
            binding=binding,
            client_ip=CLIENT_IP,
            user_agent=USER_AGENT,
        )


async def test_oauth_login_callback_rejects_a_missing_binding(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
) -> None:
    _, binding_hash = new_binding()
    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
        binding_hash=binding_hash,
    )
    use_case = _oauth_login_callback_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        event_publisher,
        session_repository,
    )

    with pytest.raises(AuthenticationError) as error:
        await use_case.execute(
            OAuthProvider.GITHUB,
            code="code",
            state=state,
            binding=None,
            client_ip=CLIENT_IP,
            user_agent=USER_AGENT,
        )

    assert error.value.code is ErrorCode.OAUTH_STATE_INVALID

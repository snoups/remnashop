from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.core.config import AppConfig
from app.core.db.models.user_session import UserSession
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, OAuthProvider, Role
from app.core.event_bus import EventBus
from app.core.events import EventCategory
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.core.ports import EventPublisher
from app.core.security import hash_password, hash_refresh_token
from app.core.security.permissions import Permission
from app.modules.auth.dto import CreateOAuthIdentityDto
from app.modules.auth.events import (
    BootstrapConflictEvent,
    LoginFailedEvent,
    LoginSucceededEvent,
    OAuthIdentityConnectedEvent,
    OAuthIdentityDisconnectedEvent,
    OAuthLoginFailedEvent,
    OAuthLoginSucceededEvent,
    OwnerBootstrappedEvent,
    SessionTheftDetectedEvent,
)
from app.modules.auth.oauth.oidc import OIDCOAuthClient
from app.modules.auth.oauth.registry import get_oauth_client
from app.modules.auth.oauth.state_store import OAuthFlowPurpose, OAuthStateStore
from app.modules.auth.repository import OAuthIdentityRepository, SessionRepository
from app.modules.auth.session_issuer import SessionIssuer
from app.modules.auth.usecases import (
    BootstrapOwnerUseCase,
    GetAuthStatusUseCase,
    ListOAuthIdentitiesUseCase,
    LoginUseCase,
    OAuthCallbackDto,
    OAuthConnectAuthorizeUseCase,
    OAuthConnectCallbackUseCase,
    OAuthDisconnectDto,
    OAuthDisconnectUseCase,
    OAuthLoginAuthorizeUseCase,
    OAuthLoginCallbackUseCase,
    oauth_connect_callback,
    oauth_login_callback,
)
from app.modules.auth.usecases.list_sessions import ListSessionsUseCase
from app.modules.auth.usecases.list_user_sessions import ListUserSessionsUseCase
from app.modules.auth.usecases.logout import LogoutUseCase
from app.modules.auth.usecases.refresh_session import RefreshSessionUseCase
from app.modules.auth.usecases.revoke_session import RevokeSessionDto, RevokeSessionUseCase
from app.modules.auth.usecases.revoke_user_session import (
    RevokeUserSessionDto,
    RevokeUserSessionUseCase,
)
from app.modules.settings import SettingsRepository, UpdateOAuthSettingsDto
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

PASSWORD = "Sup3rSecretPassw0rd1234567890"
CLIENT_IP = "203.0.113.1"
REGULAR_USER = UserDto(id=999, name="Bob", role=Role.USER, language=Locale.EN)
USER_AGENT = "pytest"


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


def _login_use_case(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
) -> LoginUseCase:
    return LoginUseCase(
        user_repository,
        config,
        event_publisher,
        SessionIssuer(session_repository, uow, config),
        settings_repository,
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
    )


async def test_bootstrap_creates_owner(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
) -> None:
    use_case = _bootstrap_use_case(
        user_repository, uow, config, event_publisher, session_repository
    )

    owner, issued = await use_case.execute(
        login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT
    )

    assert owner.login == "admin"
    assert owner.role == Role.OWNER
    assert issued.access_token


async def test_bootstrap_rejects_second_owner(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
) -> None:
    use_case = _bootstrap_use_case(
        user_repository, uow, config, event_publisher, session_repository
    )
    await use_case.execute(
        login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT
    )

    with pytest.raises(ConflictError):
        await use_case.execute(
            login="someone-else", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT
        )


async def test_db_partial_index_blocks_second_owner_row(
    user_repository: UserRepository, uow: UnitOfWork, config: AppConfig
) -> None:
    # Exercises the DB-level guard directly, bypassing the use case's own
    # exists_with_role() check -- this is what actually closes the TOCTOU race
    # between two concurrent bootstrap requests (see ux_users_single_owner).
    async def create_owner(login: str) -> None:
        await user_repository.create(
            CreateUserDto(
                login=login,
                password_hash=await hash_password(PASSWORD, config.crypt_key.get_secret_value()),
                name=login,
                role=Role.OWNER,
                language=Locale.EN,
            )
        )

    async with uow:
        await create_owner("first")
        await uow.commit()

    with pytest.raises(IntegrityError):
        async with uow:
            await create_owner("second")
            await uow.commit()


async def test_login_succeeds_with_correct_password(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
) -> None:
    await _bootstrap_use_case(
        user_repository, uow, config, event_publisher, session_repository
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)

    user, issued = await _login_use_case(
        user_repository, uow, config, event_publisher, session_repository, settings_repository
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)

    assert user.login == "admin"
    assert issued.access_token


async def test_login_rejects_wrong_password(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
) -> None:
    await _bootstrap_use_case(
        user_repository, uow, config, event_publisher, session_repository
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)

    with pytest.raises(AuthenticationError):
        await _login_use_case(
            user_repository, uow, config, event_publisher, session_repository, settings_repository
        ).execute(
            login="admin",
            password="wrong-password-here-anything",
            client_ip=CLIENT_IP,
            user_agent=USER_AGENT,
        )


async def test_login_rejects_unknown_login(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
) -> None:
    with pytest.raises(AuthenticationError):
        await _login_use_case(
            user_repository, uow, config, event_publisher, session_repository, settings_repository
        ).execute(
            login="nobody",
            password="whatever-password-here",
            client_ip=CLIENT_IP,
            user_agent=USER_AGENT,
        )


async def test_login_rejects_when_password_login_disabled(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
) -> None:
    await _bootstrap_use_case(
        user_repository, uow, config, event_publisher, session_repository
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(password_login_enabled=False)
    )

    with pytest.raises(AuthenticationError):
        await _login_use_case(
            user_repository, uow, config, event_publisher, session_repository, settings_repository
        ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)


async def test_status_reflects_owner_existence(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    settings_repository: SettingsRepository,
    session_repository: SessionRepository,
) -> None:
    status_use_case = GetAuthStatusUseCase(user_repository, settings_repository)

    result = await status_use_case.execute()
    assert not result.owner_exists

    await _bootstrap_use_case(
        user_repository, uow, config, event_publisher, session_repository
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)

    result = await status_use_case.execute()
    assert result.owner_exists


async def test_status_reflects_configured_oauth_providers(
    user_repository: UserRepository, settings_repository: SettingsRepository
) -> None:
    status_use_case = GetAuthStatusUseCase(user_repository, settings_repository)

    result = await status_use_case.execute()
    assert result.oauth_providers[OAuthProvider.GITHUB] is False
    assert result.oauth_providers[OAuthProvider.TELEGRAM] is False
    assert result.oauth_providers[OAuthProvider.OIDC] is False
    assert result.oidc_display_name is None

    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            github_client_id="gh-id",
            github_client_secret="gh-secret",
            github_enabled=True,
            oidc_issuer_url="https://keycloak.example.com/realms/myrealm",
            oidc_client_id="oidc-id",
            oidc_client_secret="oidc-secret",
            oidc_display_name="Keycloak",
        )
    )

    result = await status_use_case.execute()
    assert result.oauth_providers[OAuthProvider.GITHUB] is True
    assert result.oauth_providers[OAuthProvider.TELEGRAM] is False
    assert result.oauth_providers[OAuthProvider.OIDC] is False
    assert result.oidc_display_name is None

    await settings_repository.update_oauth_settings(UpdateOAuthSettingsDto(oidc_enabled=True))

    result = await status_use_case.execute()
    assert result.oauth_providers[OAuthProvider.OIDC] is True
    assert result.oidc_display_name == "Keycloak"


async def test_status_reflects_password_login_toggle(
    user_repository: UserRepository, settings_repository: SettingsRepository
) -> None:
    status_use_case = GetAuthStatusUseCase(user_repository, settings_repository)

    result = await status_use_case.execute()
    assert result.password_login_enabled is True

    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(password_login_enabled=False)
    )

    result = await status_use_case.execute()
    assert result.password_login_enabled is False


async def test_login_publishes_success_and_failure_events(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
) -> None:
    bus = EventBus()
    received: list[object] = []

    async def record(event: object) -> None:
        received.append(event)

    def resubscribe() -> None:
        # publish() is fire-and-forget now, and shutdown() (used below to
        # deterministically wait for dispatch) clears handlers -- re-register
        # before each action that needs them observed.
        bus.subscribe(LoginSucceededEvent, record)
        bus.subscribe(LoginFailedEvent, record)

    resubscribe()
    await _bootstrap_use_case(user_repository, uow, config, bus, session_repository).execute(
        login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT
    )
    await bus.shutdown()
    received.clear()  # drop the OwnerBootstrappedEvent side effect of setup

    resubscribe()
    await _login_use_case(
        user_repository, uow, config, bus, session_repository, settings_repository
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)
    await bus.shutdown()
    assert isinstance(received[-1], LoginSucceededEvent)
    assert received[-1].user.login == "admin"
    assert received[-1].ip_address == CLIENT_IP

    resubscribe()
    with pytest.raises(AuthenticationError):
        await _login_use_case(
            user_repository, uow, config, bus, session_repository, settings_repository
        ).execute(
            login="admin", password="wrong-one-here", client_ip=CLIENT_IP, user_agent=USER_AGENT
        )
    await bus.shutdown()
    assert isinstance(received[-1], LoginFailedEvent)
    assert received[-1].login == "admin"
    assert received[-1].ip_address == CLIENT_IP


async def test_bootstrap_publishes_owner_bootstrapped_event(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    session_repository: SessionRepository,
) -> None:
    bus = EventBus()
    received: list[object] = []

    async def record(event: object) -> None:
        received.append(event)

    bus.subscribe(OwnerBootstrappedEvent, record)

    await _bootstrap_use_case(user_repository, uow, config, bus, session_repository).execute(
        login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT
    )
    await bus.shutdown()  # deterministically wait for fire-and-forget dispatch

    assert len(received) == 1
    assert isinstance(received[0], OwnerBootstrappedEvent)
    assert received[0].user.login == "admin"
    assert received[0].ip_address == CLIENT_IP


class _StubOAuthClient:
    requires_pkce = False

    async def authorization_url(self, redirect_uri: str, state: str, code_verifier: object) -> str:
        return f"https://example.com/authorize?state={state}"

    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: object
    ) -> tuple[str, str]:
        return "external-123", "octocat"


class _FailingOAuthClient(_StubOAuthClient):
    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: object
    ) -> tuple[str, str]:
        raise KeyError("id")


async def test_oauth_login_authorize_returns_url_for_configured_provider(
    settings_repository: SettingsRepository, oauth_state_store: OAuthStateStore, config: AppConfig
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
    use_case = OAuthLoginAuthorizeUseCase(settings_repository, oauth_state_store, config)

    url = await use_case.execute(OAuthProvider.GITHUB)

    assert url.startswith("https://github.com/login/oauth/authorize")
    assert "state=" in url


async def test_oauth_login_authorize_rejects_unconfigured_provider(
    settings_repository: SettingsRepository, oauth_state_store: OAuthStateStore, config: AppConfig
) -> None:
    use_case = OAuthLoginAuthorizeUseCase(settings_repository, oauth_state_store, config)

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
    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
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
) -> None:
    monkeypatch.setattr(
        oauth_login_callback, "get_oauth_client", lambda provider, settings: _FailingOAuthClient()
    )
    bus = EventBus()
    received: list[object] = []

    async def record(event: object) -> None:
        received.append(event)

    bus.subscribe(OAuthLoginFailedEvent, record)

    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
    )
    use_case = _oauth_login_callback_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        bus,
        session_repository,
    )

    with pytest.raises(AuthenticationError):
        await use_case.execute(
            OAuthProvider.GITHUB,
            code="code",
            state=state,
            client_ip=CLIENT_IP,
            user_agent=USER_AGENT,
        )
    await bus.shutdown()  # deterministically wait for fire-and-forget dispatch

    assert len(received) == 1
    assert isinstance(received[0], OAuthLoginFailedEvent)
    assert received[0].provider is OAuthProvider.GITHUB


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
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=owner.id,
            provider=OAuthProvider.GITHUB,
            external_id="external-123",
            external_login=None,
        )
    )
    state = await oauth_state_store.create(
        provider=OAuthProvider.GITHUB,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
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

    logged_in_user, issued = await use_case.execute(
        OAuthProvider.GITHUB, code="code", state=state, client_ip=CLIENT_IP, user_agent=USER_AGENT
    )

    assert logged_in_user.id == owner.id
    assert issued.access_token


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


async def test_regular_user_cannot_connect_authorize(
    settings_repository: SettingsRepository, oauth_state_store: OAuthStateStore, config: AppConfig
) -> None:
    interactor = OAuthConnectAuthorizeUseCase(settings_repository, oauth_state_store, config)

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
    interactor = OAuthConnectAuthorizeUseCase(settings_repository, oauth_state_store, config)

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
    interactor = OAuthDisconnectUseCase(oauth_identity_repository, uow, event_publisher)

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
    interactor = OAuthDisconnectUseCase(oauth_identity_repository, uow, event_publisher)

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

    interactor = ListOAuthIdentitiesUseCase(oauth_identity_repository)
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


def test_all_auth_events_declare_auth_category() -> None:
    event_classes = [
        OwnerBootstrappedEvent,
        LoginSucceededEvent,
        LoginFailedEvent,
        BootstrapConflictEvent,
        OAuthLoginSucceededEvent,
        OAuthLoginFailedEvent,
        OAuthIdentityConnectedEvent,
        OAuthIdentityDisconnectedEvent,
    ]

    for event_class in event_classes:
        assert event_class.category == EventCategory.AUTH, event_class.__name__


async def test_refresh_rotates_and_returns_new_access_token(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    issuer = SessionIssuer(session_repository, uow, config)
    issued = await issuer.issue(owner.id, CLIENT_IP, USER_AGENT)

    use_case = RefreshSessionUseCase(session_repository, issuer, uow, event_publisher)
    refreshed = await use_case.execute(
        refresh_token=issued.refresh_token, ip_address=CLIENT_IP, user_agent=USER_AGENT
    )

    # create_access_token has no jti/nonce -- it's deterministic on
    # (user_id, session_id, exp-second), so a same-session reissue within the
    # same wall-clock second legitimately produces a byte-identical access
    # token. The refresh token is the actual, guaranteed-random signal that
    # rotation happened.
    assert refreshed.access_token
    assert refreshed.refresh_token != issued.refresh_token


async def test_refresh_within_grace_window_after_rotation_succeeds(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    issuer = SessionIssuer(session_repository, uow, config)
    issued = await issuer.issue(owner.id, CLIENT_IP, USER_AGENT)
    use_case = RefreshSessionUseCase(session_repository, issuer, uow, event_publisher)

    # First tab refreshes.
    await use_case.execute(
        refresh_token=issued.refresh_token, ip_address=CLIENT_IP, user_agent=USER_AGENT
    )
    # Second tab's request was already in flight with the now-superseded token
    # -- within the grace window this must succeed, not be treated as theft.
    second = await use_case.execute(
        refresh_token=issued.refresh_token, ip_address=CLIENT_IP, user_agent=USER_AGENT
    )

    assert second.access_token


async def test_refresh_ping_pong_reuse_of_stale_token_eventually_fails(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    issuer = SessionIssuer(session_repository, uow, config)
    issued = await issuer.issue(owner.id, CLIENT_IP, USER_AGENT)
    use_case = RefreshSessionUseCase(session_repository, issuer, uow, event_publisher)

    t0 = issued.refresh_token
    # Attacker (holds a copy of T0) refreshes first -- succeeds, gets T1.
    attacker = await use_case.execute(refresh_token=t0, ip_address=CLIENT_IP, user_agent=USER_AGENT)
    t1 = attacker.refresh_token
    # Victim, unaware, refreshes with their own still-cached T0 shortly after
    # -- this is the intended benign "second tab" race, must still succeed once.
    victim = await use_case.execute(refresh_token=t0, ip_address=CLIENT_IP, user_agent=USER_AGENT)
    t2 = victim.refresh_token
    assert t1 != t2

    # Before the fix, T1 (minted for the attacker via the fraudulent rotation)
    # kept working indefinitely because every grace-branch rotation re-armed
    # the window and shifted "previous" forward to whatever was briefly
    # current. After the fix, T1 is neither the current hash (T2 is) nor the
    # tracked previous hash (still T0's slot, untouched by the
    # extend_grace=False rotation) -- it must now be rejected.
    with pytest.raises(AuthenticationError):
        await use_case.execute(refresh_token=t1, ip_address=CLIENT_IP, user_agent=USER_AGENT)

    # The legitimate current token must still work -- a fix that broke both
    # tokens instead of just rejecting the attacker's stale one would also
    # pass the assertion above; this proves only the attacker's path failed.
    final = await use_case.execute(refresh_token=t2, ip_address=CLIENT_IP, user_agent=USER_AGENT)
    assert final.access_token


async def test_refresh_outside_grace_window_revokes_session_and_publishes_theft_event(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    owner = await _bootstrap_owner(user_repository, uow, config, EventBus(), session_repository)
    issuer = SessionIssuer(session_repository, uow, config)
    issued = await issuer.issue(owner.id, CLIENT_IP, USER_AGENT)

    bus = EventBus()
    received: list[SessionTheftDetectedEvent] = []

    async def record(event: SessionTheftDetectedEvent) -> None:
        received.append(event)

    bus.subscribe(SessionTheftDetectedEvent, record)
    use_case = RefreshSessionUseCase(session_repository, issuer, uow, bus)

    rotated = await use_case.execute(
        refresh_token=issued.refresh_token, ip_address=CLIENT_IP, user_agent=USER_AGENT
    )

    # Simulate the grace window having elapsed.
    session_row = await session_repository.get_rotatable_by_hash(
        hash_refresh_token(rotated.refresh_token)
    )
    assert session_row is not None
    await session_repository.session.execute(
        update(UserSession)
        .where(UserSession.id == session_row.id)
        .values(previous_hash_grace_until=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    await session_repository.session.flush()

    with pytest.raises(AuthenticationError):
        await use_case.execute(
            refresh_token=issued.refresh_token, ip_address=CLIENT_IP, user_agent=USER_AGENT
        )
    await bus.shutdown()

    assert await session_repository.get_active_by_id(session_row.id) is None
    assert len(received) == 1
    assert received[0].session_id == session_row.id


async def test_refresh_rejects_unknown_token(
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    issuer = SessionIssuer(session_repository, uow, config)
    use_case = RefreshSessionUseCase(session_repository, issuer, uow, event_publisher)

    with pytest.raises(AuthenticationError):
        await use_case.execute(
            refresh_token="never-issued", ip_address=CLIENT_IP, user_agent=USER_AGENT
        )


async def test_list_sessions_returns_only_actors_own(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    # _bootstrap_owner already issues one session for the owner as part of
    # bootstrap -- no need to issue a second one here.
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    async with uow:
        other = await user_repository.create(
            CreateUserDto(login="other2", name="other2", role=Role.ADMIN, language=Locale.EN)
        )
        await uow.commit()
    issuer = SessionIssuer(session_repository, uow, config)
    await issuer.issue(other.id, CLIENT_IP, USER_AGENT)

    use_case = ListSessionsUseCase(session_repository)
    sessions = await use_case(owner)

    assert len(sessions) == 1
    assert sessions[0].user_id == owner.id


async def test_revoke_session_removes_it_from_active_list(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    # _bootstrap_owner already issues one session for the owner as part of
    # bootstrap -- that's the session under test, no need to issue another.
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    sessions_before = await session_repository.list_active_by_user(owner.id)

    use_case = RevokeSessionUseCase(session_repository, uow, event_publisher)
    await use_case(owner, RevokeSessionDto(session_id=sessions_before[-1].id, client_ip=CLIENT_IP))

    assert await session_repository.list_active_by_user(owner.id) == []


async def test_revoke_session_rejects_someone_elses_session(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    async with uow:
        other = await user_repository.create(
            CreateUserDto(login="other3", name="other3", role=Role.ADMIN, language=Locale.EN)
        )
        await uow.commit()
    issuer = SessionIssuer(session_repository, uow, config)
    await issuer.issue(other.id, CLIENT_IP, USER_AGENT)
    other_sessions = await session_repository.list_active_by_user(other.id)

    use_case = RevokeSessionUseCase(session_repository, uow, event_publisher)
    with pytest.raises(NotFoundError):
        await use_case(
            owner, RevokeSessionDto(session_id=other_sessions[0].id, client_ip=CLIENT_IP)
        )


async def test_admin_can_view_and_revoke_lower_privileged_users_session(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    await _bootstrap_owner(user_repository, uow, config, event_publisher, session_repository)
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="admin-viewer",
                name="admin-viewer",
                role=Role.ADMIN,
                language=Locale.EN,
                permission_grants=[
                    Permission.USER_SESSIONS_VIEW.value,
                    Permission.USER_SESSIONS_REVOKE.value,
                ],
            )
        )
        target = await user_repository.create(
            CreateUserDto(login="plain-user", name="plain-user", role=Role.USER, language=Locale.EN)
        )
        await uow.commit()
    issuer = SessionIssuer(session_repository, uow, config)
    await issuer.issue(target.id, CLIENT_IP, USER_AGENT)
    target_session = (await session_repository.list_active_by_user(target.id))[0]

    list_use_case = ListUserSessionsUseCase(session_repository, user_repository)
    sessions = await list_use_case(admin, target.id)
    assert [s.id for s in sessions] == [target_session.id]

    revoke_use_case = RevokeUserSessionUseCase(
        session_repository, user_repository, uow, event_publisher
    )
    await revoke_use_case(
        admin,
        RevokeUserSessionDto(user_id=target.id, session_id=target_session.id, client_ip=CLIENT_IP),
    )
    assert await session_repository.list_active_by_user(target.id) == []


async def test_admin_cannot_view_or_revoke_owners_session(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="admin-attacker",
                name="admin-attacker",
                role=Role.ADMIN,
                language=Locale.EN,
                permission_grants=[
                    Permission.USER_SESSIONS_VIEW.value,
                    Permission.USER_SESSIONS_REVOKE.value,
                ],
            )
        )
        await uow.commit()
    owner_session = (await session_repository.list_active_by_user(owner.id))[0]

    list_use_case = ListUserSessionsUseCase(session_repository, user_repository)
    with pytest.raises(ConflictError):
        await list_use_case(admin, owner.id)

    revoke_use_case = RevokeUserSessionUseCase(
        session_repository, user_repository, uow, event_publisher
    )
    with pytest.raises(ConflictError):
        await revoke_use_case(
            admin,
            RevokeUserSessionDto(
                user_id=owner.id, session_id=owner_session.id, client_ip=CLIENT_IP
            ),
        )
    assert await session_repository.list_active_by_user(owner.id) == [owner_session]


async def test_logout_revokes_the_session(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    issuer = SessionIssuer(session_repository, uow, config)
    issued = await issuer.issue(owner.id, CLIENT_IP, USER_AGENT)

    use_case = LogoutUseCase(session_repository, uow)
    await use_case.execute(refresh_token=issued.refresh_token)

    # Verify the issued session is revoked by checking it's no longer found by its hash
    assert (
        await session_repository.get_rotatable_by_hash(hash_refresh_token(issued.refresh_token))
        is None
    )


async def test_logout_is_idempotent_for_unknown_token(
    session_repository: SessionRepository,
    uow: UnitOfWork,
) -> None:
    use_case = LogoutUseCase(session_repository, uow)
    await use_case.execute(refresh_token="never-issued")  # must not raise

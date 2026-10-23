from typing import Optional

import pytest

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import BlacklistKind, Locale, OAuthProvider, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError, ConflictError, ValidationError
from app.core.ports import EventPublisher
from app.modules.auth import SessionIssuer, SessionRepository
from app.modules.blacklist import BlacklistRepository
from app.modules.oauth.dto import CreateOAuthIdentityDto, OAuthCallbackDto, OAuthDisconnectDto
from app.modules.oauth.providers.base import OAuthProfile
from app.modules.oauth.providers.state_store import (
    OAuthFlowPurpose,
    OAuthStateStore,
    new_binding,
)
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.oauth.usecases import (
    ListOAuthIdentitiesUseCase,
    OAuthConnectCallbackUseCase,
    OAuthDisconnectUseCase,
    OAuthLoginCallbackUseCase,
    oauth_connect_callback,
    oauth_login_callback,
)
from app.modules.settings import SettingsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

CLIENT_IP = "203.0.113.1"
USER_AGENT = "pytest"
TELEGRAM_ID = 555


class _FakeClient:
    requires_pkce = False

    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: object
    ) -> OAuthProfile:
        return OAuthProfile(external_id=str(TELEGRAM_ID), login="tg_user")


async def _create_user(
    user_repository: UserRepository,
    uow: UnitOfWork,
    login: str,
    role: Role,
    telegram_id: Optional[int] = None,
) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=login, name=login, role=role, language=Locale.EN, telegram_id=telegram_id
            )
        )
        await uow.commit()
    return user


def _login_use_case(
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


def _connect_use_case(
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> OAuthConnectCallbackUseCase:
    return OAuthConnectCallbackUseCase(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        BlacklistRepository(user_repository.session),
        uow,
        config,
        event_publisher,
    )


async def test_telegram_login_issues_session_for_staff_user(
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
    monkeypatch.setattr(oauth_login_callback, "get_oauth_client", lambda *_: _FakeClient())
    admin = await _create_user(user_repository, uow, "adm", Role.ADMIN, TELEGRAM_ID)
    binding, binding_hash = new_binding()
    state = await oauth_state_store.create(
        provider=OAuthProvider.TELEGRAM,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
        binding_hash=binding_hash,
    )
    use_case = _login_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        event_publisher,
        session_repository,
    )

    user, issued = await use_case.execute(
        OAuthProvider.TELEGRAM,
        code="c",
        state=state,
        binding=binding,
        client_ip=CLIENT_IP,
        user_agent=USER_AGENT,
    )

    assert user.id == admin.id
    assert issued.access_token


async def test_telegram_login_rejects_non_staff_user(
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
    monkeypatch.setattr(oauth_login_callback, "get_oauth_client", lambda *_: _FakeClient())
    await _create_user(user_repository, uow, "usr", Role.USER, TELEGRAM_ID)
    binding, binding_hash = new_binding()
    state = await oauth_state_store.create(
        provider=OAuthProvider.TELEGRAM,
        purpose=OAuthFlowPurpose.LOGIN,
        user_id=None,
        code_verifier=None,
        binding_hash=binding_hash,
    )
    use_case = _login_use_case(
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
            OAuthProvider.TELEGRAM,
            code="c",
            state=state,
            binding=binding,
            client_ip=CLIENT_IP,
            user_agent=USER_AGENT,
        )

    assert error.value.code == ErrorCode.OAUTH_ACCOUNT_NOT_LINKED


async def test_github_login_rejects_non_staff_user(
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
    monkeypatch.setattr(oauth_login_callback, "get_oauth_client", lambda *_: _FakeClient())
    customer = await _create_user(user_repository, uow, "usr", Role.USER)
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=customer.id,
            provider=OAuthProvider.GITHUB,
            external_id=str(TELEGRAM_ID),
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
    use_case = _login_use_case(
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
            code="c",
            state=state,
            binding=binding,
            client_ip=CLIENT_IP,
            user_agent=USER_AGENT,
        )

    assert error.value.code == ErrorCode.OAUTH_ACCOUNT_NOT_LINKED


async def test_telegram_connect_sets_telegram_id_without_identity_row(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    monkeypatch.setattr(oauth_connect_callback, "get_oauth_client", lambda *_: _FakeClient())
    admin = await _create_user(user_repository, uow, "adm", Role.ADMIN)
    state = await oauth_state_store.create(
        provider=OAuthProvider.TELEGRAM,
        purpose=OAuthFlowPurpose.CONNECT,
        user_id=admin.id,
        code_verifier=None,
    )
    use_case = _connect_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        event_publisher,
    )

    identity = await use_case(
        admin,
        OAuthCallbackDto(
            provider=OAuthProvider.TELEGRAM, code="c", state=state, client_ip=CLIENT_IP
        ),
    )

    assert identity.external_id == str(TELEGRAM_ID)
    assert identity.external_login == "tg_user"
    async with uow:
        reloaded = await user_repository.find_by_id(admin.id)
    assert reloaded is not None
    assert reloaded.telegram_id == TELEGRAM_ID
    assert await oauth_identity_repository.list_by_user(admin.id) == []


async def test_telegram_connect_rejects_id_taken_by_another_user(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    monkeypatch.setattr(oauth_connect_callback, "get_oauth_client", lambda *_: _FakeClient())
    admin = await _create_user(user_repository, uow, "adm", Role.ADMIN)
    await _create_user(user_repository, uow, "usr", Role.USER, TELEGRAM_ID)
    state = await oauth_state_store.create(
        provider=OAuthProvider.TELEGRAM,
        purpose=OAuthFlowPurpose.CONNECT,
        user_id=admin.id,
        code_verifier=None,
    )
    use_case = _connect_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        event_publisher,
    )

    with pytest.raises(ConflictError) as error:
        await use_case(
            admin,
            OAuthCallbackDto(
                provider=OAuthProvider.TELEGRAM, code="c", state=state, client_ip=CLIENT_IP
            ),
        )

    assert error.value.code == ErrorCode.TELEGRAM_ID_TAKEN


async def test_telegram_connect_refuses_a_blacklisted_id(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    oauth_state_store: OAuthStateStore,
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    monkeypatch.setattr(oauth_connect_callback, "get_oauth_client", lambda *_: _FakeClient())
    admin = await _create_user(user_repository, uow, "adm", Role.ADMIN)
    async with uow:
        await BlacklistRepository(user_repository.session).add_entry(
            BlacklistKind.TELEGRAM_ID, str(TELEGRAM_ID)
        )
    state = await oauth_state_store.create(
        provider=OAuthProvider.TELEGRAM,
        purpose=OAuthFlowPurpose.CONNECT,
        user_id=admin.id,
        code_verifier=None,
    )
    use_case = _connect_use_case(
        settings_repository,
        oauth_state_store,
        oauth_identity_repository,
        user_repository,
        uow,
        config,
        event_publisher,
    )

    with pytest.raises(ValidationError) as error:
        await use_case(
            admin,
            OAuthCallbackDto(
                provider=OAuthProvider.TELEGRAM, code="c", state=state, client_ip=CLIENT_IP
            ),
        )

    assert error.value.code == ErrorCode.TELEGRAM_ID_BLACKLISTED


async def test_telegram_disconnect_clears_telegram_id(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    admin = await _create_user(user_repository, uow, "adm", Role.ADMIN, TELEGRAM_ID)
    use_case = OAuthDisconnectUseCase(
        oauth_identity_repository, user_repository, uow, event_publisher
    )

    await use_case(admin, OAuthDisconnectDto(provider=OAuthProvider.TELEGRAM, client_ip=CLIENT_IP))

    async with uow:
        reloaded = await user_repository.find_by_id(admin.id)
    assert reloaded is not None
    assert reloaded.telegram_id is None


async def test_telegram_disconnect_without_telegram_id_is_noop(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    admin = await _create_user(user_repository, uow, "adm", Role.ADMIN)
    use_case = OAuthDisconnectUseCase(
        oauth_identity_repository, user_repository, uow, event_publisher
    )

    await use_case(admin, OAuthDisconnectDto(provider=OAuthProvider.TELEGRAM, client_ip=CLIENT_IP))


async def test_list_includes_telegram_from_actor_telegram_id(
    user_repository: UserRepository,
    uow: UnitOfWork,
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    admin = await _create_user(user_repository, uow, "adm", Role.ADMIN, TELEGRAM_ID)
    use_case = ListOAuthIdentitiesUseCase(oauth_identity_repository, uow)

    identities = await use_case(admin)

    telegram = [i for i in identities if i.provider is OAuthProvider.TELEGRAM]
    assert len(telegram) == 1
    assert telegram[0].external_id == str(TELEGRAM_ID)

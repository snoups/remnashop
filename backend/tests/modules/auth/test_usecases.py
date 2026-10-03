from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import SyntheticActor
from app.core.config import AppConfig
from app.core.db.models import EventOutboxEntry
from app.core.db.models.user_session import UserSession
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, OAuthProvider, Role
from app.core.error_codes import ErrorCode
from app.core.events import BaseEvent, EventCategory
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
)
from app.core.ports import EventPublisher
from app.core.security import hash_password, hash_refresh_token
from app.core.security.permissions import Permission
from app.modules.auth.dto import RevokeSessionDto, RevokeUserSessionDto
from app.modules.auth.events import (
    BootstrapConflictEvent,
    LoginFailedEvent,
    LoginSucceededEvent,
    OwnerBootstrappedEvent,
    SessionTheftDetectedEvent,
)
from app.modules.auth.repository import SessionRepository
from app.modules.auth.session_issuer import SessionIssuer
from app.modules.auth.usecases import BootstrapOwnerUseCase, GetAuthStatusUseCase, LoginUseCase
from app.modules.auth.usecases.list_sessions import ListSessionsUseCase
from app.modules.auth.usecases.list_user_sessions import ListUserSessionsUseCase
from app.modules.auth.usecases.logout import LogoutUseCase
from app.modules.auth.usecases.refresh_session import RefreshSessionUseCase
from app.modules.auth.usecases.revoke_session import RevokeSessionUseCase
from app.modules.auth.usecases.revoke_user_session import RevokeUserSessionUseCase
from app.modules.oauth.events import (
    OAuthIdentityConnectedEvent,
    OAuthIdentityDisconnectedEvent,
    OAuthLoginFailedEvent,
    OAuthLoginSucceededEvent,
)
from app.modules.settings import SettingsRepository, UpdateOAuthSettingsDto
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository

PASSWORD = "Sup3rSecretPassw0rd1234567890"
CLIENT_IP = "203.0.113.1"
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
    # the DB guard itself (ux_users_single_owner), past exists_with_role(): it's
    # what closes the race between two bootstrap requests
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

    with pytest.raises(ConflictError) as exc_info:
        async with uow:
            await create_owner("second")
            await uow.commit()
    assert exc_info.value.code is ErrorCode.OWNER_ALREADY_EXISTS


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


@pytest.mark.parametrize(
    ("login", "password"),
    [
        ("x\n2026-01-01 00:00:00.000 | INFO | forged", "whatever"),
        ("a" * 65, "whatever"),
        ("nobody", "p" * 1025),
    ],
)
async def test_login_rejects_malformed_input_with_the_generic_error(
    login: str,
    password: str,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
) -> None:
    with pytest.raises(AuthenticationError, match="Invalid login or password"):
        await _login_use_case(
            user_repository, uow, config, event_publisher, session_repository, settings_repository
        ).execute(login=login, password=password, client_ip=CLIENT_IP, user_agent=USER_AGENT)


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
    status_use_case = GetAuthStatusUseCase(user_repository, settings_repository, uow)

    result = await status_use_case.execute()
    assert not result.owner_exists

    await _bootstrap_use_case(
        user_repository, uow, config, event_publisher, session_repository
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)

    result = await status_use_case.execute()
    assert result.owner_exists


async def test_status_reflects_configured_oauth_providers(
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    status_use_case = GetAuthStatusUseCase(user_repository, settings_repository, uow)

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
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    status_use_case = GetAuthStatusUseCase(user_repository, settings_repository, uow)

    result = await status_use_case.execute()
    assert result.password_login_enabled is True

    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(password_login_enabled=False)
    )

    result = await status_use_case.execute()
    assert result.password_login_enabled is False


async def test_get_auth_status_reports_passkey_login_enabled(
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    await settings_repository.update_oauth_settings(
        UpdateOAuthSettingsDto(
            passkey_enabled=True, passkey_rp_id="example.com", passkey_origin="https://example.com"
        )
    )
    use_case = GetAuthStatusUseCase(user_repository, settings_repository, uow)

    status = await use_case.execute()

    assert status.is_passkey_login_enabled is True


async def test_login_publishes_success_and_failure_events(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    session_repository: SessionRepository,
    settings_repository: SettingsRepository,
    session: AsyncSession,
    event_publisher: EventPublisher,
) -> None:
    await _bootstrap_use_case(
        user_repository, uow, config, event_publisher, session_repository
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)

    await _login_use_case(
        user_repository, uow, config, event_publisher, session_repository, settings_repository
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)

    success = await _newest_outbox_row(session, LoginSucceededEvent.__name__)
    assert success.payload["user"]["login"] == "admin"
    assert success.ip_address == CLIENT_IP

    with pytest.raises(AuthenticationError):
        await _login_use_case(
            user_repository, uow, config, event_publisher, session_repository, settings_repository
        ).execute(
            login="admin", password="wrong-one-here", client_ip=CLIENT_IP, user_agent=USER_AGENT
        )

    failure = await _newest_outbox_row(session, LoginFailedEvent.__name__)
    assert failure.payload["login"] == "admin"
    assert failure.ip_address == CLIENT_IP


async def test_bootstrap_publishes_owner_bootstrapped_event(
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    session_repository: SessionRepository,
    session: AsyncSession,
    event_publisher: EventPublisher,
) -> None:
    await _bootstrap_use_case(
        user_repository, uow, config, event_publisher, session_repository
    ).execute(login="admin", password=PASSWORD, client_ip=CLIENT_IP, user_agent=USER_AGENT)

    row = await _newest_outbox_row(session, OwnerBootstrappedEvent.__name__)
    assert row.payload["user"]["login"] == "admin"
    assert row.ip_address == CLIENT_IP


def test_all_auth_events_declare_auth_category() -> None:
    event_classes: list[type[BaseEvent]] = [
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

    # access tokens have no jti, so a reissue within the same second is
    # identical; the random refresh token shows the rotation
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
    # a second tab's request with the superseded token, inside the grace window
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
    # attacker holds a copy of T0 and refreshes first, getting T1
    attacker = await use_case.execute(refresh_token=t0, ip_address=CLIENT_IP, user_agent=USER_AGENT)
    t1 = attacker.refresh_token
    # the victim's T0 refresh right after is the benign "second tab" race and
    # must still succeed once
    victim = await use_case.execute(refresh_token=t0, ip_address=CLIENT_IP, user_agent=USER_AGENT)
    t2 = victim.refresh_token
    assert t1 != t2

    # T1 is neither the current hash (T2 is) nor the tracked previous one (still
    # T0: the grace-branch rotation doesn't shift it), so it's dead. If each
    # grace rotation re-armed the window, T1 would live forever.
    with pytest.raises(AuthenticationError):
        await use_case.execute(refresh_token=t1, ip_address=CLIENT_IP, user_agent=USER_AGENT)

    # rejecting every token would also pass the check above
    final = await use_case.execute(refresh_token=t2, ip_address=CLIENT_IP, user_agent=USER_AGENT)
    assert final.access_token


async def test_refresh_outside_grace_window_revokes_session_and_publishes_theft_event(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    session: AsyncSession,
    event_publisher: EventPublisher,
) -> None:
    owner = await _bootstrap_owner(
        user_repository, uow, config, event_publisher, session_repository
    )
    issuer = SessionIssuer(session_repository, uow, config)
    issued = await issuer.issue(owner.id, CLIENT_IP, USER_AGENT)

    use_case = RefreshSessionUseCase(session_repository, issuer, uow, event_publisher)

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

    assert await session_repository.get_active_by_id(session_row.id) is None
    row = await _newest_outbox_row(session, SessionTheftDetectedEvent.__name__)
    assert row.payload["session_id"] == session_row.id


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
    # _bootstrap_owner already issued the owner a session
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

    use_case = ListSessionsUseCase(session_repository, uow)
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
    # _bootstrap_owner's session is the one under test
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

    list_use_case = ListUserSessionsUseCase(session_repository, user_repository, uow)
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


async def test_admin_cannot_view_or_revoke_another_admins_session(
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
                login="admin-attacker-2",
                name="admin-attacker-2",
                role=Role.ADMIN,
                language=Locale.EN,
                permission_grants=[
                    Permission.USER_SESSIONS_VIEW.value,
                    Permission.USER_SESSIONS_REVOKE.value,
                ],
            )
        )
        other_admin = await user_repository.create(
            CreateUserDto(
                login="admin-target",
                name="admin-target",
                role=Role.ADMIN,
                language=Locale.EN,
            )
        )
        await uow.commit()
    issuer = SessionIssuer(session_repository, uow, config)
    await issuer.issue(other_admin.id, CLIENT_IP, USER_AGENT)
    other_admin_session = (await session_repository.list_active_by_user(other_admin.id))[0]

    list_use_case = ListUserSessionsUseCase(session_repository, user_repository, uow)
    with pytest.raises(ConflictError):
        await list_use_case(admin, other_admin.id)

    revoke_use_case = RevokeUserSessionUseCase(
        session_repository, user_repository, uow, event_publisher
    )
    with pytest.raises(ConflictError):
        await revoke_use_case(
            admin,
            RevokeUserSessionDto(
                user_id=other_admin.id, session_id=other_admin_session.id, client_ip=CLIENT_IP
            ),
        )
    assert await session_repository.list_active_by_user(other_admin.id) == [other_admin_session]


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

    list_use_case = ListUserSessionsUseCase(session_repository, user_repository, uow)
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


async def test_api_token_reaches_customer_sessions_but_not_staff_sessions(
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
        customer = await user_repository.create(
            CreateUserDto(
                login="token-target", name="token-target", role=Role.USER, language=Locale.EN
            )
        )
        await uow.commit()
    issuer = SessionIssuer(session_repository, uow, config)
    await issuer.issue(customer.id, CLIENT_IP, USER_AGENT)
    owner_sessions = await session_repository.list_active_by_user(owner.id)
    token = SyntheticActor(
        id=0,
        role=Role.USER,
        name="API Token: sessions",
        is_privileged=True,
        log="[api_token:sessions]",
        permission_grants=[
            Permission.USER_SESSIONS_VIEW.value,
            Permission.USER_SESSIONS_REVOKE.value,
        ],
    )
    list_use_case = ListUserSessionsUseCase(session_repository, user_repository, uow)
    revoke_use_case = RevokeUserSessionUseCase(
        session_repository, user_repository, uow, event_publisher
    )

    assert len(await list_use_case(token, customer.id)) == 1  # type: ignore[arg-type]
    with pytest.raises(ConflictError):
        await list_use_case(token, owner.id)  # type: ignore[arg-type]
    with pytest.raises(ConflictError):
        await revoke_use_case(
            token,  # type: ignore[arg-type]
            RevokeUserSessionDto(
                user_id=owner.id, session_id=owner_sessions[0].id, client_ip=CLIENT_IP
            ),
        )

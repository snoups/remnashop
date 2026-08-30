from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.core.db.models.user_session import UserSession
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, OAuthProvider, Role
from app.core.security import hash_refresh_token
from app.modules.auth.dto import CreateOAuthIdentityDto, CreateSessionDto, SessionDto
from app.modules.auth.repository import OAuthIdentityRepository, SessionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


async def _create_user(user_repository: UserRepository, uow: UnitOfWork, login: str) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login=login, name=login, role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()
    return user


async def test_create_then_get_by_provider_external_id(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await _create_user(user_repository, uow, "owner")

    created = await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id,
            provider=OAuthProvider.GITHUB,
            external_id="12345",
            external_login="octocat",
        )
    )
    assert created.external_id == "12345"

    found = await oauth_identity_repository.get_by_provider_external_id(
        OAuthProvider.GITHUB, "12345"
    )
    assert found is not None
    assert found.user_id == user.id
    assert found.external_login == "octocat"


async def test_get_by_provider_external_id_returns_none_when_missing(
    oauth_identity_repository: OAuthIdentityRepository,
) -> None:
    found = await oauth_identity_repository.get_by_provider_external_id(
        OAuthProvider.GITHUB, "nope"
    )
    assert found is None


async def test_create_upserts_for_same_user_and_provider(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await _create_user(user_repository, uow, "owner")

    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.GITHUB, external_id="111", external_login="old"
        )
    )
    updated = await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.GITHUB, external_id="222", external_login="new"
        )
    )

    assert updated.external_id == "222"
    identities = await oauth_identity_repository.list_by_user(user.id)
    assert len(identities) == 1
    assert identities[0].external_id == "222"


async def test_list_by_user_returns_all_providers(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await _create_user(user_repository, uow, "owner")

    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.GITHUB, external_id="111", external_login=None
        )
    )
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.TELEGRAM, external_id="222", external_login=None
        )
    )

    identities = await oauth_identity_repository.list_by_user(user.id)
    assert {identity.provider for identity in identities} == {
        OAuthProvider.GITHUB,
        OAuthProvider.TELEGRAM,
    }


async def test_delete_by_user_and_provider(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    await oauth_identity_repository.create(
        CreateOAuthIdentityDto(
            user_id=user.id, provider=OAuthProvider.GITHUB, external_id="111", external_login=None
        )
    )

    deleted = await oauth_identity_repository.delete_by_user_and_provider(
        user.id, OAuthProvider.GITHUB
    )
    assert deleted

    identities = await oauth_identity_repository.list_by_user(user.id)
    assert identities == []


async def test_delete_by_user_and_provider_returns_false_when_missing(
    oauth_identity_repository: OAuthIdentityRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    deleted = await oauth_identity_repository.delete_by_user_and_provider(
        user.id, OAuthProvider.GITHUB
    )
    assert not deleted


def _future(seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


async def _create_session(
    session_repository: SessionRepository, user_id: int, token: str = "session-token"
) -> SessionDto:
    return await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(token),
            ip_address="203.0.113.1",
            user_agent="pytest",
            expires_at=_future(30 * 24 * 3600),
        )
    )


async def test_create_then_get_active_by_id(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")

    created = await _create_session(session_repository, user.id)
    found = await session_repository.get_active_by_id(created.id)

    assert found is not None
    assert found.user_id == user.id


async def test_get_active_by_id_excludes_revoked(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id)

    await session_repository.revoke_by_id(created.id)

    assert await session_repository.get_active_by_id(created.id) is None


async def test_get_active_by_id_excludes_expired(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token("expired-token"),
            ip_address="203.0.113.1",
            user_agent=None,
            expires_at=_future(-60),  # already expired
        )
    )

    assert await session_repository.get_active_by_id(session.id) is None


async def test_get_rotatable_by_hash_matches_current_hash(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "current-token")

    found = await session_repository.get_rotatable_by_hash(hash_refresh_token("current-token"))

    assert found is not None
    assert found.id == created.id


async def test_get_rotatable_by_hash_matches_previous_within_grace(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "old-token")

    await session_repository.rotate(created.id, hash_refresh_token("new-token"))

    found = await session_repository.get_rotatable_by_hash(hash_refresh_token("old-token"))
    assert found is not None
    assert found.id == created.id


async def test_get_by_current_hash_matches_current(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "current-token")

    found = await session_repository.get_by_current_hash(hash_refresh_token("current-token"))

    assert found is not None
    assert found.id == created.id


async def test_get_by_current_hash_ignores_previous_hash(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "old-token")
    await session_repository.rotate(created.id, hash_refresh_token("new-token"))

    found = await session_repository.get_by_current_hash(hash_refresh_token("old-token"))

    assert found is None


async def test_rotate_does_not_extend_grace_when_extend_grace_is_false(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "t0")

    # First rotation: legitimate "current hash matched" case -- arms the grace
    # window so a same-moment second tab holding "t0" can still succeed once.
    await session_repository.rotate(created.id, hash_refresh_token("t1"), extend_grace=True)
    row_after_first = await session_repository.session.get(UserSession, created.id)
    assert row_after_first is not None
    first_grace_until = row_after_first.previous_hash_grace_until
    assert row_after_first.previous_refresh_token_hash == hash_refresh_token("t0")

    # Second rotation happens via the grace-window branch (someone reused the
    # stale "t0") -- must NOT re-arm the window or move the tracked stale hash
    # forward, otherwise reuse detection never triggers.
    await session_repository.rotate(created.id, hash_refresh_token("t2"), extend_grace=False)
    row_after_second = await session_repository.session.get(UserSession, created.id)
    assert row_after_second is not None
    assert row_after_second.previous_refresh_token_hash == hash_refresh_token("t0")
    assert row_after_second.previous_hash_grace_until == first_grace_until
    assert row_after_second.refresh_token_hash == hash_refresh_token("t2")


async def test_get_rotatable_by_hash_rejects_previous_after_grace_expires(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "old-token")
    await session_repository.rotate(created.id, hash_refresh_token("new-token"))

    # Manually push the grace window into the past to simulate elapsed time
    # without sleeping in the test.
    await session_repository.session.execute(
        update(UserSession)
        .where(UserSession.id == created.id)
        .values(previous_hash_grace_until=_future(-1))
    )
    await session_repository.session.flush()

    found = await session_repository.get_rotatable_by_hash(hash_refresh_token("old-token"))
    assert found is None


async def test_get_by_expired_previous_hash_matches_only_after_grace_elapses(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "old-token")
    await session_repository.rotate(created.id, hash_refresh_token("new-token"))

    # Still within grace -- must NOT match yet.
    assert (
        await session_repository.get_by_expired_previous_hash(hash_refresh_token("old-token"))
        is None
    )

    await session_repository.session.execute(
        update(UserSession)
        .where(UserSession.id == created.id)
        .values(previous_hash_grace_until=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    await session_repository.session.flush()

    found = await session_repository.get_by_expired_previous_hash(hash_refresh_token("old-token"))
    assert found is not None
    assert found.id == created.id


async def test_rotate_updates_hash_and_last_used_at(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "old-token")

    rotated = await session_repository.rotate(created.id, hash_refresh_token("new-token"))

    assert rotated.last_used_at >= created.last_used_at
    found_by_new = await session_repository.get_rotatable_by_hash(hash_refresh_token("new-token"))
    assert found_by_new is not None
    assert found_by_new.id == created.id


async def test_list_active_by_user_excludes_revoked(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    kept = await _create_session(session_repository, user.id, "kept-token")
    revoked = await _create_session(session_repository, user.id, "revoked-token")
    await session_repository.revoke_by_id(revoked.id)

    sessions = await session_repository.list_active_by_user(user.id)

    assert [s.id for s in sessions] == [kept.id]


async def test_revoke_all_by_user_revokes_every_active_session(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    await _create_session(session_repository, user.id, "token-1")
    await _create_session(session_repository, user.id, "token-2")

    await session_repository.revoke_all_by_user(user.id)

    assert await session_repository.list_active_by_user(user.id) == []

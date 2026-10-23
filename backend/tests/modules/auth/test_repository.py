from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.core.db.models.user_session import UserSession
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import hash_refresh_token
from app.modules.auth.dto import CreateSessionDto, SessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


async def _create_user(user_repository: UserRepository, uow: UnitOfWork, login: str) -> UserDto:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login=login, name=login, role=Role.OWNER, language=Locale.EN)
        )
        await uow.commit()
    return user


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
            audience=SessionAudience.DASHBOARD,
        )
    )


async def test_create_then_get_active_by_id(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")

    created = await _create_session(session_repository, user.id)
    found = await session_repository.find_active_by_id(created.id)

    assert found is not None
    assert found.user_id == user.id


async def test_get_active_by_id_excludes_revoked(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id)

    await session_repository.revoke_by_id(created.id)

    assert await session_repository.find_active_by_id(created.id) is None


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
            expires_at=_future(-60),  # already expired,
            audience=SessionAudience.DASHBOARD,
        )
    )

    assert await session_repository.find_active_by_id(session.id) is None


async def test_get_rotatable_by_hash_matches_current_hash(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "current-token")

    found = await session_repository.find_rotatable_by_hash(hash_refresh_token("current-token"))

    assert found is not None
    assert found.id == created.id


async def test_get_rotatable_by_hash_matches_previous_within_grace(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "old-token")

    await session_repository.rotate(created.id, hash_refresh_token("new-token"))

    found = await session_repository.find_rotatable_by_hash(hash_refresh_token("old-token"))
    assert found is not None
    assert found.id == created.id


async def test_get_by_current_hash_matches_current(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "current-token")

    found = await session_repository.find_by_current_hash(hash_refresh_token("current-token"))

    assert found is not None
    assert found.id == created.id


async def test_get_by_current_hash_ignores_previous_hash(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "old-token")
    await session_repository.rotate(created.id, hash_refresh_token("new-token"))

    found = await session_repository.find_by_current_hash(hash_refresh_token("old-token"))

    assert found is None


async def test_rotate_does_not_extend_grace_when_extend_grace_is_false(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "t0")

    # first rotation matches the current hash and arms the grace window for a
    # second tab still holding "t0"
    await session_repository.rotate(created.id, hash_refresh_token("t1"), extend_grace=True)
    row_after_first = await session_repository.session.get(UserSession, created.id)
    assert row_after_first is not None
    first_grace_until = row_after_first.previous_hash_grace_until
    assert row_after_first.previous_refresh_token_hash == hash_refresh_token("t0")

    # second rotation reuses "t0" via the grace branch and must not re-arm the
    # window or move the stale hash, or reuse detection never fires
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

    found = await session_repository.find_rotatable_by_hash(hash_refresh_token("old-token"))
    assert found is None


async def test_get_by_expired_previous_hash_matches_only_after_grace_elapses(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "old-token")
    await session_repository.rotate(created.id, hash_refresh_token("new-token"))

    # still within grace
    assert (
        await session_repository.find_by_expired_previous_hash(hash_refresh_token("old-token"))
        is None
    )

    await session_repository.session.execute(
        update(UserSession)
        .where(UserSession.id == created.id)
        .values(previous_hash_grace_until=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    await session_repository.session.flush()

    found = await session_repository.find_by_expired_previous_hash(hash_refresh_token("old-token"))
    assert found is not None
    assert found.id == created.id


async def test_rotate_updates_hash_and_last_used_at(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "owner")
    created = await _create_session(session_repository, user.id, "old-token")

    rotated = await session_repository.rotate(created.id, hash_refresh_token("new-token"))

    assert rotated.last_used_at >= created.last_used_at
    found_by_new = await session_repository.find_rotatable_by_hash(hash_refresh_token("new-token"))
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


async def test_revoke_all_by_user_can_keep_the_current_session(
    session_repository: SessionRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    user = await _create_user(user_repository, uow, "keeper")
    current = await _create_session(session_repository, user.id, "token-current")
    await _create_session(session_repository, user.id, "token-other")

    await session_repository.revoke_all_by_user(user.id, keep_session_id=current.id)

    assert [s.id for s in await session_repository.list_active_by_user(user.id)] == [current.id]

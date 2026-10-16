"""Races the route-level tests can't show: their requests share one AsyncSession,
where a row lock serializes nothing. Each use case here gets its own connection;
the seed rows are committed and removed by hand."""

import asyncio
import contextlib
from typing import AsyncIterator, Awaitable, Callable

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db.models import User
from app.core.db.uow import UnitOfWork
from app.core.exceptions import ConflictError
from app.modules.account_merge import CustomerAccountMerger
from app.modules.account_merge.repository import AccountMergeRepository
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist.repository import BlacklistRepository
from app.modules.identity_links.dto import IdentityClaimDto, IdentityKind
from app.modules.identity_links.linker import IdentityLinker
from app.modules.identity_links.merge_tokens import MergeTokenStore
from app.modules.identity_links.usecases import ConfirmMergeUseCase, UnlinkIdentityUseCase
from app.modules.oauth import OAuthProfile
from app.modules.oauth.repository import OAuthIdentityRepository
from app.modules.settings.repository import SettingsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.events import RecordingEventPublisher


@pytest.fixture
def created() -> list[int]:
    return []


@pytest.fixture
async def sessions(
    engine: AsyncEngine, created: list[int]
) -> AsyncIterator[Callable[[], Awaitable[AsyncSession]]]:
    async with contextlib.AsyncExitStack() as stack:

        async def open_session() -> AsyncSession:
            conn = await stack.enter_async_context(engine.connect())
            session = AsyncSession(bind=conn, expire_on_commit=False)
            stack.push_async_callback(session.close)
            return session

        yield open_session
    async with engine.begin() as cleanup:
        await cleanup.execute(delete(User).where(User.id.in_(created)))


async def _seed(session: AsyncSession, created: list[int], **fields: object) -> UserDto:
    user = await UserRepository(session).create(CreateUserDto(**fields))
    await session.commit()
    created.append(user.id)
    return user


async def _outcome(call: Awaitable[object]) -> str:
    try:
        await call
        return "ok"
    except ConflictError as error:
        return str(error.code)


async def test_parallel_unlinks_keep_one_method(sessions, created: list[int]) -> None:
    user = await _seed(
        await sessions(),
        created,
        name="race-unlink",
        telegram_id=97_001,
        email="race-unlink@gmail.com",
    )

    def unlink(session: AsyncSession) -> UnlinkIdentityUseCase:
        return UnlinkIdentityUseCase(
            UserRepository(session),
            OAuthIdentityRepository(session),
            RecordingEventPublisher(),
            UnitOfWork(session),
        )

    first, second = await sessions(), await sessions()
    results = await asyncio.gather(
        _outcome(unlink(first).execute(user, IdentityKind.TELEGRAM, "127.0.0.1")),
        _outcome(unlink(second).execute(user, IdentityKind.EMAIL, "127.0.0.1")),
    )

    assert sorted(results) == ["LAST_SIGN_IN_METHOD", "ok"]
    fresh = await UserRepository(await sessions()).find_by_id(user.id)
    assert fresh is not None
    assert (fresh.telegram_id is None) != (fresh.email is None)


async def test_parallel_merge_single_effect(sessions, created: list[int], redis: Redis) -> None:
    setup = await sessions()
    current = await _seed(setup, created, name="race-current", telegram_id=97_002)
    other = await _seed(setup, created, name="race-other", email="race-other@gmail.com")
    token = await MergeTokenStore(redis).issue(
        current.id,
        other.id,
        IdentityClaimDto(kind=IdentityKind.EMAIL, email="race-other@gmail.com"),
    )

    def confirm(session: AsyncSession) -> ConfirmMergeUseCase:
        users, uow, publisher = (
            UserRepository(session),
            UnitOfWork(session),
            RecordingEventPublisher(),
        )
        oauth = OAuthIdentityRepository(session)
        merger = CustomerAccountMerger(
            users, AccountMergeRepository(session), SessionRepository(session), uow, publisher
        )
        tokens = MergeTokenStore(redis)
        linker = IdentityLinker(
            users,
            oauth,
            BlacklistRepository(session),
            SettingsRepository(session),
            merger,
            tokens,
            publisher,
            uow,
        )
        return ConfirmMergeUseCase(tokens, linker, merger, users, uow)

    first, second = await sessions(), await sessions()
    results = await asyncio.gather(
        _outcome(confirm(first).execute(current, token, "127.0.0.1")),
        _outcome(confirm(second).execute(current, token, "127.0.0.1")),
    )

    assert sorted(results) == ["MERGE_TOKEN_INVALID", "ok"]
    check = UserRepository(await sessions())
    merged = await check.find_by_id(current.id)
    assert merged is not None and merged.email == "race-other@gmail.com"
    gone = await check.find_by_id(other.id)
    assert gone is not None and gone.deleted_at is not None


async def test_merge_token_oauth_claim_round_trip(redis: Redis) -> None:
    claim = IdentityClaimDto(
        kind=IdentityKind.GOOGLE,
        oauth=OAuthProfile(
            external_id="g-1", login="ann", email="a@gmail.com", email_verified=True
        ),
    )
    tokens = MergeTokenStore(redis)
    token = await tokens.issue(1, 2, claim)

    ticket = await tokens.take(token)

    assert ticket is not None and ticket.claim == claim
    assert (ticket.user_id, ticket.other_user_id) == (1, 2)
    assert await tokens.take(token) is None

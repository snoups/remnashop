from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import (
    EventOutboxEntry,
    OAuthIdentity,
    Referral,
    Subscription,
    Transaction,
    User,
)
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider, SessionAudience
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.account_merge import CustomerAccountMerger
from app.modules.account_merge.repository import AccountMergeRepository
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.broadcasts.factories import add_paid_transaction, add_subscription


@pytest.fixture
def merger(
    session: AsyncSession,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> CustomerAccountMerger:
    return CustomerAccountMerger(
        user_repository, AccountMergeRepository(session), session_repository, uow, event_publisher
    )


async def _login(session_repository: SessionRepository, user_id: int) -> None:
    await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=f"customer-merge-{user_id}",
            ip_address="10.0.0.1",
            user_agent=None,
            expires_at=datetime_now() + timedelta(days=1),
            audience=SessionAudience.CABINET,
        )
    )


async def _pair(user_repository: UserRepository, **other: object) -> tuple[UserDto, UserDto]:
    current = await user_repository.create(CreateUserDto(name="current", email="me@x.io"))
    second = await user_repository.create(CreateUserDto(name="other", **other))
    return current, second


async def _count(session: AsyncSession, model: type, column: object, user_id: int) -> int:
    return int(
        await session.scalar(select(func.count()).select_from(model).where(column == user_id)) or 0
    )


async def test_merge_moves_everything_into_current(
    merger, session: AsyncSession, user_repository
) -> None:
    current, other = await _pair(user_repository, telegram_id=777)
    await add_subscription(session, other.id)
    await add_paid_transaction(session, other.id)
    invited = await user_repository.create(CreateUserDto(name="invited"))
    session.add(Referral(referrer_id=other.id, referred_id=invited.id, level=1))
    await session.flush()

    merged = await merger.merge(current, other.id, "127.0.0.1")

    assert merged.id == current.id and merged.telegram_id == 777 and merged.name == "current"
    for model, column in (
        (Subscription, Subscription.user_id),
        (Transaction, Transaction.user_id),
        (Referral, Referral.referrer_id),
    ):
        assert await _count(session, model, column, current.id) == 1
        assert await _count(session, model, column, other.id) == 0
    gone = await user_repository.find_by_id(other.id)
    assert gone is not None and gone.deleted_at is not None and gone.telegram_id is None


async def test_merge_moves_oauth_identity(merger, session: AsyncSession, user_repository) -> None:
    current, other = await _pair(user_repository)
    session.add(OAuthIdentity(user_id=other.id, provider=OAuthProvider.GITHUB, external_id="gh"))
    await session.flush()

    await merger.merge(current, other.id, "127.0.0.1")

    assert await session.scalar(select(OAuthIdentity.user_id)) == current.id


async def test_merge_revokes_only_other_sessions(
    merger, user_repository, session_repository
) -> None:
    current, other = await _pair(user_repository)
    await _login(session_repository, current.id)
    await _login(session_repository, other.id)

    await merger.merge(current, other.id, "127.0.0.1")

    assert len(await session_repository.list_active_by_user(current.id)) == 1
    assert await session_repository.list_active_by_user(other.id) == []


async def test_merge_sums_points_and_spends_trial(
    merger, session: AsyncSession, user_repository
) -> None:
    current, other = await _pair(user_repository)
    await user_repository.credit_points(current.id, Decimal(3))
    await user_repository.credit_points(other.id, Decimal(4))
    await user_repository.credit_bonus_days(other.id, 5)
    await session.execute(update(User).where(User.id == other.id).values(is_trial_available=False))
    await session.flush()

    merged = await merger.merge(current, other.id, "127.0.0.1")

    assert merged.points == Decimal(7) and merged.bonus_days == 5
    assert merged.is_trial_available is False


async def test_merge_publishes_accounts_merged_with_customer_actor(
    merger, session: AsyncSession, user_repository
) -> None:
    current, other = await _pair(user_repository)

    await merger.merge(current, other.id, "127.0.0.1")

    row = (
        await session.scalars(
            select(EventOutboxEntry).where(EventOutboxEntry.event_type == "AccountsMergedEvent")
        )
    ).one()
    assert row.actor_id == current.id
    assert row.payload["target"]["id"] == current.id
    assert row.payload["source"]["id"] == other.id


async def test_merge_exceeding_subscription_limit_is_allowed(
    merger, session: AsyncSession, user_repository
) -> None:
    current, other = await _pair(user_repository)
    await add_subscription(session, current.id)
    await add_subscription(session, other.id)

    await merger.merge(current, other.id, "127.0.0.1")

    assert await _count(session, Subscription, Subscription.user_id, current.id) == 2


async def test_merge_rechecks_under_lock(merger, session: AsyncSession, user_repository) -> None:
    current, other = await _pair(user_repository)
    await add_subscription(session, other.id)
    assert (await merger.check(current, other.id)).subscriptions == 1
    await session.execute(update(User).where(User.id == other.id).values(is_blocked=True))
    await session.flush()

    with pytest.raises(ConflictError) as error:
        await merger.merge(current, other.id, "127.0.0.1")

    # the uow rolled back, so nothing was reassigned or anonymized
    assert error.value.code == ErrorCode.MERGE_ACCOUNT_BLOCKED
    assert await session.scalar(select(func.count()).select_from(EventOutboxEntry)) == 0

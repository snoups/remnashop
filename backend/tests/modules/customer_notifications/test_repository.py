from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import CustomerNotification
from app.core.utils.time import datetime_now
from app.modules.customer_notifications.repository import CustomerNotificationRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
def repository(session: AsyncSession) -> CustomerNotificationRepository:
    return CustomerNotificationRepository(session)


async def _add(repository, user_id: int, outbox_id: int, event_type: str = "e") -> None:
    await repository.add(
        user_id=user_id,
        outbox_id=outbox_id,
        event_type=event_type,
        args={"n": outbox_id},
        subscription_id=None,
    )


async def test_add_is_idempotent_per_outbox(
    session: AsyncSession, user_repository: UserRepository, repository
) -> None:
    user = await user_repository.create(CreateUserDto(name="u"))

    await _add(repository, user.id, 1)
    await _add(repository, user.id, 1)

    assert await session.scalar(select(func.count()).select_from(CustomerNotification)) == 1


async def test_list_recent_is_own_newest_first_and_limited(
    session: AsyncSession, user_repository: UserRepository, repository
) -> None:
    me = await user_repository.create(CreateUserDto(name="me"))
    other = await user_repository.create(CreateUserDto(name="other"))
    for outbox_id in (1, 2, 3):
        await _add(repository, me.id, outbox_id)
        await session.execute(
            update(CustomerNotification)
            .where(CustomerNotification.outbox_id == outbox_id)
            .values(created_at=datetime_now() - timedelta(hours=10 - outbox_id))
        )
    await _add(repository, other.id, 4)

    items = await repository.list_recent(me.id, since=datetime_now() - timedelta(days=1), limit=2)

    assert [i.args["n"] for i in items] == [3, 2]


async def test_count_unread_and_mark_all_read(user_repository: UserRepository, repository) -> None:
    user = await user_repository.create(CreateUserDto(name="u"))
    await _add(repository, user.id, 1)
    await _add(repository, user.id, 2)
    since = datetime_now() - timedelta(days=1)
    assert await repository.count_unread(user.id, since=since) == 2

    await repository.mark_all_read(user.id)

    assert await repository.count_unread(user.id, since=since) == 0


async def test_delete_older_than(
    session: AsyncSession, user_repository: UserRepository, repository
) -> None:
    user = await user_repository.create(CreateUserDto(name="u"))
    await _add(repository, user.id, 1)
    await _add(repository, user.id, 2)
    await session.execute(
        update(CustomerNotification)
        .where(CustomerNotification.outbox_id == 1)
        .values(created_at=datetime_now() - timedelta(days=100))
    )

    deleted = await repository.delete_older_than(datetime_now() - timedelta(days=90))

    assert deleted == 1
    [left] = (await session.scalars(select(CustomerNotification))).all()
    assert left.outbox_id == 2

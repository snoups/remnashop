import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.uow import UnitOfWork


async def test_after_commit_waits_for_the_commit(session: AsyncSession) -> None:
    uow = UnitOfWork(session)
    ran: list[str] = []

    async def callback() -> None:
        ran.append("ran")

    async with uow:
        await uow.after_commit(callback)
        assert ran == []

    assert ran == ["ran"]


async def test_after_commit_is_dropped_on_rollback(session: AsyncSession) -> None:
    uow = UnitOfWork(session)
    ran: list[str] = []

    async def callback() -> None:
        ran.append("ran")

    with pytest.raises(RuntimeError):
        async with uow:
            await uow.after_commit(callback)
            raise RuntimeError("abort")

    async with uow:
        pass

    assert ran == []


async def test_after_commit_outside_a_transaction_runs_at_once(session: AsyncSession) -> None:
    uow = UnitOfWork(session)
    ran: list[str] = []

    async def callback() -> None:
        ran.append("ran")

    await uow.after_commit(callback)

    assert ran == ["ran"]

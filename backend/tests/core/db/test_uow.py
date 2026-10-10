import pytest
from sqlalchemy import select
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


async def test_failed_commit_rolls_back_and_drops_callbacks(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    uow = UnitOfWork(session)
    ran: list[str] = []
    rollbacks: list[str] = []
    real_commit = session.commit
    real_rollback = session.rollback

    async def failing_commit() -> None:
        monkeypatch.setattr(session, "commit", real_commit)
        raise RuntimeError("commit lost")

    async def recording_rollback() -> None:
        rollbacks.append("rollback")
        await real_rollback()

    async def callback() -> None:
        ran.append("ran")

    monkeypatch.setattr(session, "commit", failing_commit)
    monkeypatch.setattr(session, "rollback", recording_rollback)

    with pytest.raises(RuntimeError, match="commit lost"):
        async with uow:
            await uow.after_commit(callback)

    assert rollbacks == ["rollback"]
    assert ran == []
    async with uow:
        await session.execute(select(1))

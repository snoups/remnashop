import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db.models import EventLogEntry, EventOutboxEntry
from app.core.events import EventCategory
from app.modules.event_log.outbox_repository import EventOutboxRepository


def _make_entry(**overrides: object) -> EventOutboxEntry:
    defaults: dict[str, object] = {
        "category": EventCategory.AUTH,
        "event_type": "LoginSucceededEvent",
        "occurred_at": datetime.now(timezone.utc),
        "payload": {},
        "attempts": 0,
    }
    defaults.update(overrides)
    return EventOutboxEntry(**defaults)  # type: ignore[arg-type]


async def test_list_unprocessed_excludes_processed_rows(session) -> None:
    repo = EventOutboxRepository(session)
    processed = _make_entry()
    unprocessed = _make_entry()
    session.add_all([processed, unprocessed])
    await session.flush()
    processed.processed_at = datetime.now(timezone.utc)
    await session.flush()

    rows = await repo.list_unprocessed_ids(limit=10)

    assert rows == [unprocessed.id]


async def test_list_unprocessed_excludes_rows_at_the_attempt_cap(session) -> None:
    repo = EventOutboxRepository(session)
    poisoned = _make_entry(attempts=5)
    session.add(poisoned)
    await session.flush()

    rows = await repo.list_unprocessed_ids(limit=10)

    assert rows == []


async def test_get_unprocessed_by_id_returns_none_once_processed(session) -> None:
    repo = EventOutboxRepository(session)
    entry = _make_entry()
    session.add(entry)
    await session.flush()

    await repo.mark_processed(entry.id)

    assert await repo.find_unprocessed_by_id(entry.id) is None


async def test_record_failure_increments_attempts_and_stores_error(session) -> None:
    repo = EventOutboxRepository(session)
    entry = _make_entry()
    session.add(entry)
    await session.flush()

    await repo.record_failure(entry.id, error="boom")
    row = await repo.find_unprocessed_by_id(entry.id)

    assert row is not None
    assert row.attempts == 1
    assert row.last_error == "boom"


async def test_get_unprocessed_by_id_skips_a_row_locked_by_another_transaction(
    engine: AsyncEngine,
) -> None:
    async with engine.connect() as conn_a, engine.connect() as conn_b:
        session_a = AsyncSession(bind=conn_a, expire_on_commit=False)
        session_b = AsyncSession(bind=conn_b, expire_on_commit=False)
        repo_a = EventOutboxRepository(session_a)
        repo_b = EventOutboxRepository(session_b)

        entry = EventOutboxEntry(
            category=EventCategory.AUTH,
            event_type="LoginSucceededEvent",
            occurred_at=datetime.now(timezone.utc),
            payload={},
            attempts=0,
        )
        session_a.add(entry)
        await session_a.commit()
        entry_id = entry.id

        try:
            await session_a.begin()
            locked = await repo_a.find_unprocessed_by_id(entry_id)
            assert locked is not None  # conn_a now holds the row lock

            # conn_b must not block and must not see the row
            skipped = await asyncio.wait_for(repo_b.find_unprocessed_by_id(entry_id), timeout=1.0)
            assert skipped is None

            await session_a.rollback()  # release the lock

            # now conn_b sees it
            seen = await repo_b.find_unprocessed_by_id(entry_id)
            assert seen is not None
        finally:
            await session_a.close()
            await session_b.close()  # release the FOR UPDATE lock before the cleanup DELETE
            async with engine.begin() as cleanup:
                await cleanup.execute(
                    delete(EventOutboxEntry).where(EventOutboxEntry.id == entry_id)
                )


async def test_delete_processed_before_removes_only_old_processed_rows(
    session: AsyncSession,
) -> None:
    repo = EventOutboxRepository(session)
    now = datetime.now(timezone.utc)

    old_processed = _make_entry(processed_at=now - timedelta(days=30))
    recent_processed = _make_entry(processed_at=now - timedelta(days=1))
    old_unprocessed = _make_entry(
        occurred_at=now - timedelta(days=30), attempts=5, processed_at=None
    )
    session.add_all([old_processed, recent_processed, old_unprocessed])
    await session.flush()

    deleted = await repo.delete_processed_before(now - timedelta(days=14))

    assert deleted == 1
    remaining = set((await session.scalars(select(EventOutboxEntry.id))).all())
    assert remaining == {recent_processed.id, old_unprocessed.id}


async def test_delete_processed_before_nulls_the_audit_link_but_keeps_the_audit_row(
    session: AsyncSession,
) -> None:
    repo = EventOutboxRepository(session)
    now = datetime.now(timezone.utc)
    outbox = _make_entry(processed_at=now - timedelta(days=30))
    session.add(outbox)
    await session.flush()
    audit = EventLogEntry(
        category=EventCategory.AUTH,
        event_type="LoginSucceededEvent",
        occurred_at=now,
        payload={},
        outbox_id=outbox.id,
    )
    session.add(audit)
    await session.flush()

    await repo.delete_processed_before(now - timedelta(days=14))

    await session.refresh(audit)
    assert audit.outbox_id is None
    assert await session.get(EventLogEntry, audit.id) is not None


async def test_count_poisoned_counts_only_unprocessed_rows_at_the_attempt_cap(
    session: AsyncSession,
) -> None:
    repo = EventOutboxRepository(session)
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            _make_entry(attempts=5),
            _make_entry(attempts=5, processed_at=now),
            _make_entry(attempts=2),
        ]
    )
    await session.flush()

    assert await repo.count_poisoned() == 1


async def test_get_lag_stats_returns_zero_and_none_when_empty(session) -> None:
    repo = EventOutboxRepository(session)

    stats = await repo.get_lag_stats()

    assert stats.unprocessed_count == 0
    assert stats.oldest_occurred_at is None


async def test_get_lag_stats_counts_unprocessed_and_finds_the_oldest(session) -> None:
    repo = EventOutboxRepository(session)
    older = _make_entry(occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    newer = _make_entry(occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    poisoned = _make_entry(occurred_at=datetime(2026, 1, 3, tzinfo=timezone.utc), attempts=5)
    processed = _make_entry(occurred_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
    session.add_all([older, newer, poisoned, processed])
    await session.flush()
    processed.processed_at = datetime.now(timezone.utc)
    await session.flush()

    stats = await repo.get_lag_stats()

    assert stats.unprocessed_count == 3
    assert stats.oldest_occurred_at == older.occurred_at

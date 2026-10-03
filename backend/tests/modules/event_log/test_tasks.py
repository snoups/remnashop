from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.event_bus import EventBus
from app.core.events import EventCategory
from app.modules.auth.events import LoginFailedEvent
from app.modules.event_log.outbox_repository import EventOutboxRepository, OutboxLagStats
from app.modules.event_log.repository import EventLogRepository
from app.modules.event_log.tasks import (
    OUTBOX_OLDEST_AGE,
    OUTBOX_UNPROCESSED,
    _record_outbox_lag_metrics,
    prune_outbox_task,
)
from app.modules.event_log.usecases import ProcessOutboxEntryUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
def outbox_repository(session) -> EventOutboxRepository:
    return EventOutboxRepository(session)


async def test_process_outbox_entry_persists_and_marks_processed(
    event_log_repository: EventLogRepository,
    outbox_repository: EventOutboxRepository,
    user_repository: UserRepository,
    session,
    uow: UnitOfWork,
) -> None:
    target = await user_repository.create(CreateUserDto(name="Target", login="target"))
    entry = EventOutboxEntry(
        category=EventCategory.ADMIN_MANAGEMENT,
        event_type="AdminCreatedEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={"target": {"id": target.id}},
        attempts=0,
    )
    session.add(entry)
    await session.flush()
    bus = EventBus()

    await ProcessOutboxEntryUseCase(outbox_repository, event_log_repository, bus, uow).system(
        entry.id
    )

    items, total = await event_log_repository.list()
    assert total == 1
    assert items[0].outbox_id == entry.id
    assert items[0].target_id == target.id
    row = await outbox_repository.get_unprocessed_by_id(entry.id)
    assert row is None  # marked processed


async def test_process_outbox_entry_records_failure_when_a_handler_raises(
    event_log_repository: EventLogRepository,
    outbox_repository: EventOutboxRepository,
    session,
    uow: UnitOfWork,
) -> None:
    entry = EventOutboxEntry(
        category=EventCategory.AUTH,
        event_type="LoginFailedEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={"login": "x"},
        attempts=0,
    )
    session.add(entry)
    await session.flush()
    bus = EventBus()

    async def failing_handler(stored_event: object) -> None:
        raise RuntimeError("boom")

    bus.subscribe(LoginFailedEvent, failing_handler)

    await ProcessOutboxEntryUseCase(outbox_repository, event_log_repository, bus, uow).system(
        entry.id
    )

    row = await outbox_repository.get_unprocessed_by_id(entry.id)
    assert row is not None  # NOT marked processed
    assert row.processed_at is None
    assert row.attempts == 1
    assert row.last_error == "boom"
    # the audit row commits with record_failure even when the handler fails;
    # the next sweep re-dispatches, idempotent on outbox_id
    items, total = await event_log_repository.list()
    assert total == 1
    assert items[0].outbox_id == entry.id


async def test_process_outbox_entry_is_a_noop_when_already_processed(
    event_log_repository: EventLogRepository,
    outbox_repository: EventOutboxRepository,
    session,
    uow: UnitOfWork,
) -> None:
    entry = EventOutboxEntry(
        category=EventCategory.AUTH,
        event_type="LoginFailedEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={"login": "x"},
        attempts=0,
    )
    session.add(entry)
    await session.flush()
    await outbox_repository.mark_processed(entry.id)
    bus = EventBus()

    await ProcessOutboxEntryUseCase(outbox_repository, event_log_repository, bus, uow).system(
        entry.id
    )

    items, _ = await event_log_repository.list()
    assert items == []  # get_unprocessed_by_id returned None, nothing persisted


async def test_sweep_processes_good_rows_even_when_a_sibling_row_fails(
    event_log_repository: EventLogRepository,
    outbox_repository: EventOutboxRepository,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    good = EventOutboxEntry(
        category=EventCategory.AUTH,
        event_type="LoginSucceededEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={},
        attempts=0,
    )
    bad = EventOutboxEntry(
        category=EventCategory.AUTH,
        event_type="LoginFailedEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={"login": "x"},
        attempts=0,
    )
    session.add_all([good, bad])
    await session.flush()
    await session.commit()  # survive each per-row rollback
    good_id, bad_id = good.id, bad.id

    bus = EventBus()

    async def failing_handler(entry: object) -> None:
        raise RuntimeError("boom")

    bus.subscribe(LoginFailedEvent, failing_handler)

    for entry_id in (good_id, bad_id):
        await ProcessOutboxEntryUseCase(outbox_repository, event_log_repository, bus, uow).system(
            entry_id
        )

    good_row = await session.get(EventOutboxEntry, good_id)
    bad_row = await session.get(EventOutboxEntry, bad_id)
    await session.refresh(good_row)
    await session.refresh(bad_row)
    assert good_row.processed_at is not None
    assert bad_row.processed_at is None
    assert bad_row.attempts == 1
    assert bad_row.last_error == "boom"
    items, total = await event_log_repository.list()
    assert total == 2  # both rows' audit entries persist; bad row just isn't marked processed


async def test_process_outbox_entry_records_failure_when_persist_raises_a_db_error(
    event_log_repository: EventLogRepository,
    outbox_repository: EventOutboxRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = EventOutboxEntry(
        category=EventCategory.AUTH,
        event_type="LoginSucceededEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={},
        attempts=0,
    )
    session.add(entry)
    await session.flush()
    await session.commit()
    entry_id = entry.id

    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated persist failure")

    monkeypatch.setattr(event_log_repository, "create", boom)
    bus = EventBus()

    await ProcessOutboxEntryUseCase(outbox_repository, event_log_repository, bus, uow).system(
        entry_id
    )

    row = await session.get(EventOutboxEntry, entry_id)
    await session.refresh(row)
    assert row.attempts == 1
    assert "simulated persist failure" in (row.last_error or "")
    assert row.processed_at is None


async def test_process_outbox_entry_retry_succeeds_without_doubling_the_audit_row(
    event_log_repository: EventLogRepository,
    outbox_repository: EventOutboxRepository,
    session,
    uow: UnitOfWork,
) -> None:
    entry = EventOutboxEntry(
        category=EventCategory.AUTH,
        event_type="LoginFailedEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={"login": "x"},
        attempts=0,
    )
    session.add(entry)
    await session.flush()

    bus = EventBus()
    calls = {"n": 0}

    async def flaky_handler(stored_event: object) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")

    bus.subscribe(LoginFailedEvent, flaky_handler)

    await ProcessOutboxEntryUseCase(outbox_repository, event_log_repository, bus, uow).system(
        entry.id
    )
    row = await outbox_repository.get_unprocessed_by_id(entry.id)
    assert row is not None
    assert row.attempts == 1

    await ProcessOutboxEntryUseCase(outbox_repository, event_log_repository, bus, uow).system(
        entry.id
    )

    items, total = await event_log_repository.list()
    assert total == 1  # idempotent on outbox_id, the retry doesn't double it
    processed = await session.get(EventOutboxEntry, entry.id)
    await session.refresh(processed)
    assert processed.processed_at is not None


def test_prune_outbox_task_carries_a_schedule_label() -> None:
    assert prune_outbox_task.labels.get("schedule")


def test_record_outbox_lag_metrics_sets_count_and_age() -> None:
    oldest = datetime.now(timezone.utc) - timedelta(seconds=90)

    _record_outbox_lag_metrics(OutboxLagStats(unprocessed_count=3, oldest_occurred_at=oldest))

    assert OUTBOX_UNPROCESSED._value.get() == 3
    assert OUTBOX_OLDEST_AGE._value.get() >= 90


def test_record_outbox_lag_metrics_zeroes_age_when_nothing_is_unprocessed() -> None:
    _record_outbox_lag_metrics(OutboxLagStats(unprocessed_count=0, oldest_occurred_at=None))

    assert OUTBOX_UNPROCESSED._value.get() == 0
    assert OUTBOX_OLDEST_AGE._value.get() == 0

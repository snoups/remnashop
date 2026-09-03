from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.event_log import EventLogEntry
from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.events import EventCategory
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def test_create_and_read_event_log_entry(
    session: AsyncSession, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    # actor_id has a real FK to users.id -- an actual row is needed to satisfy it.
    async with uow:
        owner = await user_repository.create(
            CreateUserDto(name="owner", role=Role.OWNER, language=Locale.EN, login="owner")
        )
        await uow.commit()

    entry = EventLogEntry(
        category=EventCategory.ADMIN_MANAGEMENT,
        event_type="AdminCreatedEvent",
        occurred_at=datetime.now(timezone.utc),
        actor_id=owner.id,
        actor_login="owner",
        actor_name="owner",
        ip_address="127.0.0.1",
        payload={"target": {"id": 2, "login": "newadmin"}},
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)

    assert entry.id is not None
    assert entry.category == EventCategory.ADMIN_MANAGEMENT
    assert entry.payload["target"]["login"] == "newadmin"


async def test_event_log_entry_actor_fields_are_nullable(session: AsyncSession) -> None:
    entry = EventLogEntry(
        category=EventCategory.AUTH,
        event_type="LoginFailedEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={"login": "someone"},
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)

    assert entry.actor_id is None
    assert entry.actor_login is None
    assert entry.ip_address is None


async def test_event_log_entry_outbox_id_accepts_none_and_int(session: AsyncSession) -> None:
    outbox_entry = EventOutboxEntry(
        category=EventCategory.AUTH,
        event_type="LoginFailedEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={"login": "someone"},
    )
    session.add(outbox_entry)
    await session.flush()

    linked = EventLogEntry(
        category=EventCategory.AUTH,
        event_type="LoginFailedEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={"login": "someone"},
        outbox_id=outbox_entry.id,
    )
    unlinked = EventLogEntry(
        category=EventCategory.AUTH,
        event_type="LoginFailedEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={"login": "someone"},
    )
    session.add_all([linked, unlinked])
    await session.flush()

    assert linked.outbox_id == outbox_entry.id
    assert unlinked.outbox_id is None


async def test_event_log_entry_outbox_id_is_unique(session: AsyncSession) -> None:
    outbox_entry = EventOutboxEntry(
        category=EventCategory.AUTH,
        event_type="LoginFailedEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={"login": "someone"},
    )
    session.add(outbox_entry)
    await session.flush()

    session.add(
        EventLogEntry(
            category=EventCategory.AUTH,
            event_type="LoginFailedEvent",
            occurred_at=datetime.now(timezone.utc),
            payload={"login": "someone"},
            outbox_id=outbox_entry.id,
        )
    )
    await session.flush()

    session.add(
        EventLogEntry(
            category=EventCategory.AUTH,
            event_type="LoginFailedEvent",
            occurred_at=datetime.now(timezone.utc),
            payload={"login": "someone"},
            outbox_id=outbox_entry.id,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()

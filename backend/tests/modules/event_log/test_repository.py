from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.events import EventCategory
from app.modules.event_log.dto import EventLogEntryDto
from app.modules.event_log.repository import EventLogRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


def _entry(**overrides: Any) -> EventLogEntryDto:
    defaults: dict[str, Any] = {
        "category": EventCategory.AUTH,
        "event_type": "LoginSucceededEvent",
        "occurred_at": datetime.now(timezone.utc),
        "actor_id": None,
        "actor_login": None,
        "actor_name": None,
        "ip_address": None,
        "payload": {},
    }
    defaults.update(overrides)
    return EventLogEntryDto(**defaults)


async def test_create_and_list(event_log_repository: EventLogRepository) -> None:
    await event_log_repository.create(_entry())

    items, total = await event_log_repository.list()

    assert total == 1
    assert len(items) == 1
    assert items[0].event_type == "LoginSucceededEvent"


async def test_list_filters_by_category(event_log_repository: EventLogRepository) -> None:
    await event_log_repository.create(_entry(category=EventCategory.AUTH))
    await event_log_repository.create(
        _entry(category=EventCategory.ADMIN_MANAGEMENT, event_type="AdminCreatedEvent")
    )

    items, total = await event_log_repository.list(category=EventCategory.ADMIN_MANAGEMENT)

    assert total == 1
    assert items[0].event_type == "AdminCreatedEvent"


async def test_list_filters_by_search_login(
    event_log_repository: EventLogRepository, user_repository: UserRepository
) -> None:
    owner = await user_repository.create(CreateUserDto(name="Owner", login="owner"))
    admin = await user_repository.create(CreateUserDto(name="Admin", login="admin"))
    await event_log_repository.create(_entry(actor_id=owner.id, actor_login="owner"))
    await event_log_repository.create(_entry(actor_id=admin.id, actor_login="admin"))

    items, total = await event_log_repository.list(search="owner")

    assert total == 1
    assert items[0].actor_login == "owner"


async def test_list_filters_by_search_name(event_log_repository: EventLogRepository) -> None:
    await event_log_repository.create(_entry(actor_name="Ivan Petrov"))
    await event_log_repository.create(_entry(actor_name="Someone Else"))

    items, total = await event_log_repository.list(search="petrov")

    assert total == 1
    assert items[0].actor_name == "Ivan Petrov"


async def test_list_filters_by_search_actor_id(
    event_log_repository: EventLogRepository, user_repository: UserRepository
) -> None:
    owner = await user_repository.create(CreateUserDto(name="Owner", login="owner"))
    admin = await user_repository.create(CreateUserDto(name="Admin", login="admin"))
    await event_log_repository.create(_entry(actor_id=owner.id, actor_login="owner"))
    await event_log_repository.create(_entry(actor_id=admin.id, actor_login="admin"))

    items, total = await event_log_repository.list(search=str(owner.id))

    assert total == 1
    assert items[0].actor_login == "owner"


async def test_list_filters_by_date_range(event_log_repository: EventLogRepository) -> None:
    now = datetime.now(timezone.utc)
    await event_log_repository.create(_entry(occurred_at=now - timedelta(days=10)))
    await event_log_repository.create(_entry(occurred_at=now))

    items, total = await event_log_repository.list(date_from=now - timedelta(days=1))

    assert total == 1


async def test_list_orders_newest_first(event_log_repository: EventLogRepository) -> None:
    now = datetime.now(timezone.utc)
    older = await event_log_repository.create(_entry(occurred_at=now - timedelta(minutes=5)))
    newer = await event_log_repository.create(_entry(occurred_at=now))

    items, _ = await event_log_repository.list()

    assert [i.id for i in items] == [newer.id, older.id]


async def test_list_paginates(event_log_repository: EventLogRepository) -> None:
    for _ in range(5):
        await event_log_repository.create(_entry())

    items, total = await event_log_repository.list(page=1, page_size=2)

    assert total == 5
    assert len(items) == 2


async def test_create_with_outbox_id_is_idempotent(
    event_log_repository: EventLogRepository,
) -> None:
    outbox_entry = EventOutboxEntry(
        category=EventCategory.AUTH,
        event_type="LoginSucceededEvent",
        occurred_at=datetime.now(timezone.utc),
        payload={},
    )
    event_log_repository.session.add(outbox_entry)
    await event_log_repository.session.flush()

    entry = _entry(outbox_id=outbox_entry.id)

    first = await event_log_repository.create(entry)
    second = await event_log_repository.create(entry)

    assert first is not None
    assert second is None
    items, total = await event_log_repository.list()
    assert total == 1

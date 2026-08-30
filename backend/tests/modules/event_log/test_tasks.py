from datetime import datetime, timezone

from app.core.events import EventCategory
from app.modules.event_log.repository import EventLogRepository
from app.modules.event_log.tasks import persist_event_entry
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def test_persist_event_entry_writes_to_the_repository(
    event_log_repository: EventLogRepository,
    user_repository: UserRepository,
) -> None:
    owner = await user_repository.create(CreateUserDto(name="Owner", login="owner"))

    await persist_event_entry(
        event_log_repository,
        category=EventCategory.ADMIN_MANAGEMENT,
        event_type="AdminCreatedEvent",
        occurred_at=datetime.now(timezone.utc),
        actor_id=owner.id,
        actor_login="owner",
        actor_name="owner",
        ip_address="127.0.0.1",
        payload={"target": {"id": 2}},
    )

    items, total = await event_log_repository.list()

    assert total == 1
    assert items[0].event_type == "AdminCreatedEvent"
    assert items[0].payload == {"target": {"id": 2}}

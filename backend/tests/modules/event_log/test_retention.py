import importlib
import pkgutil
from datetime import datetime, timedelta, timezone
from typing import Any

import app.modules
from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.event_bus import EventBus
from app.core.events import BaseEvent, EventCategory
from app.core.exceptions import NotFoundError
from app.modules.event_log.dto import EventLogEntryDto
from app.modules.event_log.outbox_repository import EventOutboxRepository
from app.modules.event_log.repository import EventLogRepository
from app.modules.event_log.retention import SHORT_RETENTION, SHORT_RETENTION_EVENT_TYPES
from app.modules.event_log.usecases import ProcessOutboxEntryUseCase, PruneEventLogUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository

# subscription events kept for good: money and access
_KEPT_SUBSCRIPTION_EVENTS = {
    "PanelSyncCompletedEvent",
    "PanelSyncStartedEvent",
    "AddOnChangedEvent",
    "SubscriptionAddOnGrantedEvent",
    "SubscriptionChangedEvent",
    "SubscriptionConfigSyncedEvent",
    "SubscriptionEditedEvent",
    "SubscriptionGrantedEvent",
    "SubscriptionPlanChangedByAdminEvent",
    "SubscriptionPurchasedEvent",
    "SubscriptionRenewedEvent",
    "SubscriptionRevokedEvent",
}


def _event_classes() -> dict[str, type[BaseEvent]]:
    for module in pkgutil.iter_modules(app.modules.__path__):
        try:
            importlib.import_module(f"app.modules.{module.name}.events")
        except ModuleNotFoundError:
            pass
    found: dict[str, type[BaseEvent]] = {}
    pending = list(BaseEvent.__subclasses__())
    while pending:
        cls = pending.pop()
        pending.extend(cls.__subclasses__())
        # the abstract bases declare category without a value
        if hasattr(cls, "category"):
            found[cls.__name__] = cls
    return found


def test_every_short_retention_name_is_a_real_event() -> None:
    assert SHORT_RETENTION_EVENT_TYPES <= _event_classes().keys()


def test_every_infrastructure_and_subscription_event_is_placed() -> None:
    # a new noisy event must be added to the short list, or here, knowingly
    for name, cls in _event_classes().items():
        if cls.category is EventCategory.INFRASTRUCTURE:
            assert name in SHORT_RETENTION_EVENT_TYPES, name
        if cls.category is EventCategory.SUBSCRIPTION:
            assert (name in SHORT_RETENTION_EVENT_TYPES) != (name in _KEPT_SUBSCRIPTION_EVENTS), (
                name
            )


async def _entry(
    repository: EventLogRepository, event_type: str, occurred_at: datetime, **fields: Any
) -> int:
    created = await repository.create(
        EventLogEntryDto(
            category=EventCategory.SUBSCRIPTION,
            event_type=event_type,
            occurred_at=occurred_at,
            **{"payload": {}, **fields},
        )
    )
    assert created is not None and created.id is not None
    return created.id


async def test_prune_drops_only_old_short_retention_entries(
    event_log_repository: EventLogRepository, uow: UnitOfWork
) -> None:
    now = datetime.now(timezone.utc)
    old = now - SHORT_RETENTION - timedelta(days=1)
    old_noise = await _entry(event_log_repository, "SubscriptionDeviceAddedEvent", old)
    fresh_noise = await _entry(event_log_repository, "SubscriptionDeviceAddedEvent", now)
    old_purchase = await _entry(event_log_repository, "SubscriptionPurchasedEvent", old)

    await PruneEventLogUseCase(event_log_repository, uow).system()

    async def exists(entry_id: int) -> bool:
        try:
            await event_log_repository.get_by_id(entry_id)
        except NotFoundError:
            return False
        return True

    assert not await exists(old_noise)
    assert await exists(fresh_noise) and await exists(old_purchase)


async def test_deleting_a_customer_anonymizes_their_log_entries(
    event_log_repository: EventLogRepository,
    user_repository: UserRepository,
    session,
    uow: UnitOfWork,
) -> None:
    customer = await user_repository.create(
        CreateUserDto(name="Jane", telegram_id=7_771_001, email="jane@example.com")
    )
    admin = await user_repository.create(CreateUserDto(name="Admin", login="admin-7771"))
    jane = {"id": customer.id, "name": "Jane", "email": "jane@example.com", "role": "USER"}
    own = await _entry(
        event_log_repository,
        "SubscriptionPurchasedEvent",
        datetime.now(timezone.utc),
        actor_id=customer.id,
        actor_name="Jane",
        actor_email="jane@example.com",
        ip_address="203.0.113.7",
        target_id=customer.id,
        payload={"user": jane},
    )
    deletion = EventOutboxEntry(
        category=EventCategory.USER,
        event_type="UserDeletedEvent",
        occurred_at=datetime.now(timezone.utc),
        actor_id=admin.id,
        actor_name="Admin",
        payload={"actor": {"id": admin.id, "name": "Admin"}, "target": jane},
        attempts=0,
    )
    session.add(deletion)
    await session.flush()

    await ProcessOutboxEntryUseCase(
        EventOutboxRepository(session), event_log_repository, EventBus(), uow
    ).system(deletion.id)

    mine = await event_log_repository.get_by_id(own)
    assert (mine.actor_name, mine.actor_email, mine.ip_address) == (None, None, None)
    assert mine.payload["user"] == {"id": customer.id, "role": "USER"}
    about, _ = await event_log_repository.list(target_id=customer.id, page_size=100)
    (logged,) = [e for e in about if e.outbox_id == deletion.id]
    assert logged.payload["target"] == {"id": customer.id, "role": "USER"}
    # the admin who deleted the account stays on record
    assert logged.actor_name == "Admin"
    assert logged.payload["actor"] == {"id": admin.id, "name": "Admin"}

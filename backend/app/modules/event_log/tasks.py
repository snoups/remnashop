from datetime import datetime
from typing import Any, Optional

from dishka.integrations.taskiq import FromDishka, inject

from app.core.db.uow import UnitOfWork
from app.core.events import EventCategory
from app.modules.event_log.dto import EventLogEntryDto
from app.modules.event_log.repository import EventLogRepository
from app.worker.broker import broker


async def persist_event_entry(
    repository: EventLogRepository,
    *,
    category: EventCategory,
    event_type: str,
    occurred_at: datetime,
    payload: dict[str, Any],
    actor_id: Optional[int] = None,
    actor_login: Optional[str] = None,
    actor_name: Optional[str] = None,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    await repository.create(
        EventLogEntryDto(
            category=category,
            event_type=event_type,
            occurred_at=occurred_at,
            actor_id=actor_id,
            actor_login=actor_login,
            actor_name=actor_name,
            actor_email=actor_email,
            ip_address=ip_address,
            payload=payload,
        )
    )


@broker.task
@inject(patch_module=True)
async def persist_event_task(
    category: str,
    event_type: str,
    occurred_at: str,
    payload: dict[str, Any],
    repository: FromDishka[EventLogRepository],
    uow: FromDishka[UnitOfWork],
    actor_id: Optional[int] = None,
    actor_login: Optional[str] = None,
    actor_name: Optional[str] = None,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    async with uow:
        await persist_event_entry(
            repository,
            category=EventCategory(category),
            event_type=event_type,
            occurred_at=datetime.fromisoformat(occurred_at),
            payload=payload,
            actor_id=actor_id,
            actor_login=actor_login,
            actor_name=actor_name,
            actor_email=actor_email,
            ip_address=ip_address,
        )

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.events import EventCategory
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.event_log.dto import DEFAULT_PAGE_SIZE, EventLogEntryDto
from app.modules.event_log.repository import EventLogRepository


@dataclass(frozen=True, kw_only=True)
class ListEventLogInput:
    category: Optional[EventCategory] = None
    actor_id: Optional[int] = None
    search: Optional[str] = None
    occurred_from: Optional[datetime] = None
    occurred_to: Optional[datetime] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


class ListEventLogUseCase(UseCase[ListEventLogInput, tuple[list[EventLogEntryDto], int]]):
    required_permission = Permission.EVENT_LOG_VIEW

    def __init__(self, event_log_repository: EventLogRepository, uow: UnitOfWork) -> None:
        self._event_log_repository = event_log_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListEventLogInput
    ) -> tuple[list[EventLogEntryDto], int]:
        async with self._uow:
            return await self._event_log_repository.list(
                category=data.category,
                actor_id=data.actor_id,
                search=data.search,
                occurred_from=data.occurred_from,
                occurred_to=data.occurred_to,
                page=data.page,
                page_size=data.page_size,
            )

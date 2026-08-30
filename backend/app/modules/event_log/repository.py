from datetime import datetime
from typing import Callable, Optional

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.event_log import EventLogEntry
from app.core.dto import SERVER_OWNED_FIELDS
from app.core.events import EventCategory
from app.modules.event_log.dto import DEFAULT_PAGE_SIZE, EventLogEntryDto


class EventLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

        self._convert_to_dto: Callable[[EventLogEntry], EventLogEntryDto] = (
            lambda row: EventLogEntryDto.model_validate(row, from_attributes=True)
        )

    async def create(self, entry: EventLogEntryDto) -> EventLogEntryDto:
        entry_data = entry.model_dump(exclude=SERVER_OWNED_FIELDS)
        db_entry = EventLogEntry(**entry_data)

        self.session.add(db_entry)
        await self.session.flush()

        return self._convert_to_dto(db_entry)

    async def list(
        self,
        *,
        category: Optional[EventCategory] = None,
        search: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[EventLogEntryDto], int]:
        filters: list[ColumnElement[bool]] = []
        if category is not None:
            filters.append(EventLogEntry.category == category)
        if search:
            pattern = f"%{search}%"
            search_filters: list[ColumnElement[bool]] = [
                EventLogEntry.actor_login.ilike(pattern),
                EventLogEntry.actor_name.ilike(pattern),
                EventLogEntry.actor_email.ilike(pattern),
            ]
            if search.isdigit():
                search_filters.append(EventLogEntry.actor_id == int(search))
            filters.append(or_(*search_filters))
        if date_from is not None:
            filters.append(EventLogEntry.occurred_at >= date_from)
        if date_to is not None:
            filters.append(EventLogEntry.occurred_at <= date_to)

        count_stmt = select(func.count()).select_from(EventLogEntry).where(*filters)
        total = await self.session.scalar(count_stmt)

        stmt = (
            select(EventLogEntry)
            .where(*filters)
            .order_by(EventLogEntry.occurred_at.desc(), EventLogEntry.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()

        return [self._convert_to_dto(row) for row in rows], int(total or 0)

import builtins
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import INT32_MAX
from app.core.db.models.event_log import EventLogEntry
from app.core.db.models.user import User
from app.core.db.user_search import user_search_filter
from app.core.dto import SERVER_OWNED_FIELDS
from app.core.events import EventCategory
from app.modules.event_log.dto import DEFAULT_PAGE_SIZE, EventLogEntryDto


def _notification_filters(
    event_types: frozenset[str], exclude_actor_id: int
) -> list[ColumnElement[bool]]:
    # an admin's own actions aren't news to them
    return [
        EventLogEntry.event_type.in_(event_types),
        or_(EventLogEntry.actor_id.is_(None), EventLogEntry.actor_id != exclude_actor_id),
    ]


class EventLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

        self._convert_to_dto: Callable[[EventLogEntry], EventLogEntryDto] = (
            lambda row: EventLogEntryDto.model_validate(row, from_attributes=True)
        )

    async def create(self, entry: EventLogEntryDto) -> Optional[EventLogEntryDto]:
        entry_data = entry.model_dump(exclude=SERVER_OWNED_FIELDS)
        stmt = (
            pg_insert(EventLogEntry)
            .values(**entry_data)
            .on_conflict_do_nothing(index_elements=["outbox_id"])
            .returning(EventLogEntry)
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        await self.session.flush()
        return self._convert_to_dto(row) if row is not None else None

    async def list(
        self,
        *,
        category: Optional[EventCategory] = None,
        actor_id: Optional[int] = None,
        search: Optional[str] = None,
        occurred_from: Optional[datetime] = None,
        occurred_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[EventLogEntryDto], int]:
        filters: list[ColumnElement[bool]] = []
        if category is not None:
            filters.append(EventLogEntry.category == category)
        if actor_id is not None:
            filters.append(EventLogEntry.actor_id == actor_id)
        if search:
            pattern = f"%{search}%"
            search_filters: list[ColumnElement[bool]] = [
                EventLogEntry.actor_login.ilike(pattern),
                EventLogEntry.actor_name.ilike(pattern),
                EventLogEntry.actor_email.ilike(pattern),
                # snapshots carry no telegram_id/username and go stale on rename
                EventLogEntry.actor_id.in_(select(User.id).where(user_search_filter(search))),
            ]
            # actor_id is a plain Integer FK (users.id), not BigInteger -- a longer
            # digit string is a valid `search` value but out of range for the DB
            # type, and would otherwise raise NumericValueOutOfRange from asyncpg.
            if search.isdigit() and int(search) <= INT32_MAX:
                search_filters.append(EventLogEntry.actor_id == int(search))
            filters.append(or_(*search_filters))
        if occurred_from is not None:
            filters.append(EventLogEntry.occurred_at >= occurred_from)
        if occurred_to is not None:
            filters.append(EventLogEntry.occurred_at < occurred_to)

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

    async def list_notifications(
        self,
        *,
        event_types: frozenset[str],
        exclude_actor_id: int,
        limit: int,
        after: Optional[datetime] = None,
    ) -> builtins.list[EventLogEntryDto]:
        filters = _notification_filters(event_types, exclude_actor_id)
        if after is not None:
            filters.append(EventLogEntry.occurred_at > after)
        stmt = (
            select(EventLogEntry)
            .where(*filters)
            .order_by(EventLogEntry.occurred_at.desc(), EventLogEntry.id.desc())
            .limit(limit)
        )
        return [self._convert_to_dto(row) for row in (await self.session.scalars(stmt))]

    async def count_notifications_since(
        self, *, event_types: frozenset[str], exclude_actor_id: int, since: Optional[datetime]
    ) -> int:
        filters = _notification_filters(event_types, exclude_actor_id)
        if since is not None:
            filters.append(EventLogEntry.occurred_at > since)
        stmt = select(func.count()).select_from(EventLogEntry).where(*filters)
        return await self.session.scalar(stmt) or 0

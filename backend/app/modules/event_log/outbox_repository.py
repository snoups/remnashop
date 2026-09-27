from datetime import datetime
from typing import Final, NamedTuple, Optional, cast

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.utils.time import datetime_now

_MAX_ATTEMPTS: Final[int] = 5


class OutboxLagStats(NamedTuple):
    unprocessed_count: int
    oldest_occurred_at: Optional[datetime]


class EventOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_unprocessed_by_id(self, entry_id: int) -> Optional[EventOutboxEntry]:
        # No _MAX_ATTEMPTS cap here, unlike list_unprocessed_ids: the fast path
        # fires once per publish and never retries. A future re-enqueue path must
        # gate on attempts itself or route through list_unprocessed_ids.
        stmt = (
            select(EventOutboxEntry)
            .where(EventOutboxEntry.id == entry_id, EventOutboxEntry.processed_at.is_(None))
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        row: Optional[EventOutboxEntry] = await self.session.scalar(stmt)
        return row

    async def list_unprocessed_ids(self, *, limit: int) -> list[int]:
        stmt = (
            select(EventOutboxEntry.id)
            .where(
                EventOutboxEntry.processed_at.is_(None),
                EventOutboxEntry.attempts < _MAX_ATTEMPTS,
            )
            .order_by(EventOutboxEntry.id)
            .limit(limit)
        )
        return list((await self.session.scalars(stmt)).all())

    async def mark_processed(self, entry_id: int) -> None:
        row = await self.session.get(EventOutboxEntry, entry_id)
        if row is not None:
            row.processed_at = datetime_now()
            await self.session.flush()

    async def delete_processed_before(self, cutoff: datetime) -> int:
        # event_log_entries.outbox_id is ondelete="SET NULL": this nulls the
        # audit-row link but keeps the audit row -- audit history is never pruned here.
        stmt = delete(EventOutboxEntry).where(
            EventOutboxEntry.processed_at.is_not(None),
            EventOutboxEntry.processed_at < cutoff,
        )
        result = await self.session.execute(stmt)
        return cast(CursorResult, result).rowcount

    async def count_poisoned(self) -> int:
        stmt = (
            select(func.count())
            .select_from(EventOutboxEntry)
            .where(
                EventOutboxEntry.processed_at.is_(None),
                EventOutboxEntry.attempts >= _MAX_ATTEMPTS,
            )
        )
        return await self.session.scalar(stmt) or 0

    async def record_failure(self, entry_id: int, *, error: str) -> None:
        row = await self.session.get(EventOutboxEntry, entry_id)
        if row is not None:
            row.attempts += 1
            row.last_error = error
            await self.session.flush()

    async def get_lag_stats(self) -> OutboxLagStats:
        # Includes rows past _MAX_ATTEMPTS (poisoned) on purpose -- the whole
        # backlog is what an operator needs to see, not just what the next
        # sweep will retry. count_poisoned() already covers that breakdown.
        stmt = select(func.count(), func.min(EventOutboxEntry.occurred_at)).where(
            EventOutboxEntry.processed_at.is_(None)
        )
        count, oldest = (await self.session.execute(stmt)).one()
        return OutboxLagStats(unprocessed_count=count, oldest_occurred_at=oldest)

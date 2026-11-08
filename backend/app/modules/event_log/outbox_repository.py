from datetime import datetime
from typing import Final, NamedTuple, Optional, cast

from sqlalchemy import CursorResult, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.utils.time import datetime_now
from app.modules.event_log.retention import anonymize_snapshots

_MAX_ATTEMPTS: Final[int] = 5


class OutboxLagStats(NamedTuple):
    unprocessed_count: int
    oldest_occurred_at: Optional[datetime]


class EventOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_unprocessed_by_id(self, entry_id: int) -> Optional[EventOutboxEntry]:
        # no _MAX_ATTEMPTS cap: the fast path fires once per publish, never retries
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
        # event_log_entries.outbox_id is SET NULL, so the audit rows stay
        stmt = delete(EventOutboxEntry).where(
            EventOutboxEntry.processed_at.is_not(None),
            EventOutboxEntry.processed_at < cutoff,
        )
        result = await self.session.execute(stmt)
        return cast(CursorResult, result).rowcount

    async def anonymize_user(self, user_id: int) -> None:
        # rows still here (14 days) carry the same snapshots as the audit log
        await self.session.execute(
            update(EventOutboxEntry)
            .where(EventOutboxEntry.actor_id == user_id)
            .values(actor_login=None, actor_name=None, actor_email=None, ip_address=None)
            # rows loaded in this session (the outbox entry being processed) keep their values
            .execution_options(synchronize_session=False)
        )
        await anonymize_snapshots(self.session, EventOutboxEntry, user_id)

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

    async def get_stuck_stats(self, before: datetime) -> OutboxLagStats:
        # poisoned rows are left out: the sweep no longer retries them
        stmt = select(func.count(), func.min(EventOutboxEntry.occurred_at)).where(
            EventOutboxEntry.processed_at.is_(None),
            EventOutboxEntry.attempts < _MAX_ATTEMPTS,
            EventOutboxEntry.occurred_at < before,
        )
        count, oldest = (await self.session.execute(stmt)).one()
        return OutboxLagStats(unprocessed_count=count, oldest_occurred_at=oldest)

    async def record_failure(self, entry_id: int, *, error: str) -> None:
        row = await self.session.get(EventOutboxEntry, entry_id)
        if row is not None:
            row.attempts += 1
            row.last_error = error
            await self.session.flush()

    async def get_lag_stats(self) -> OutboxLagStats:
        # poisoned rows (past _MAX_ATTEMPTS) included: the operator wants the
        # whole backlog; count_poisoned() gives the breakdown
        stmt = select(func.count(), func.min(EventOutboxEntry.occurred_at)).where(
            EventOutboxEntry.processed_at.is_(None)
        )
        count, oldest = (await self.session.execute(stmt)).one()
        return OutboxLagStats(unprocessed_count=count, oldest_occurred_at=oldest)

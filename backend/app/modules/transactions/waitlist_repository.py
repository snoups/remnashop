from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.filters import in_ids
from app.core.db.models.payment_waitlist import PaymentWaitlistEntry


class WaitlistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: int) -> None:
        await self.session.execute(
            pg_insert(PaymentWaitlistEntry).values(user_id=user_id).on_conflict_do_nothing()
        )

    async def claim_batch(self, limit: int, exclude: set[int]) -> list[int]:
        # row locks keep a concurrent broadcast off these users until commit
        query = select(PaymentWaitlistEntry.user_id)
        if exclude:
            query = query.where(PaymentWaitlistEntry.user_id.not_in(exclude))
        result = await self.session.scalars(
            query.order_by(PaymentWaitlistEntry.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result)

    async def remove(self, user_ids: set[int]) -> None:
        if user_ids:
            await self.session.execute(
                delete(PaymentWaitlistEntry).where(in_ids(PaymentWaitlistEntry.user_id, user_ids))
            )

    async def count(self) -> int:
        return (
            await self.session.scalar(select(func.count()).select_from(PaymentWaitlistEntry)) or 0
        )


class WaitlistClaims:
    """A transaction of its own per broadcast batch, apart from the request
    UnitOfWork: the send path commits that one, which would release the
    claimed rows mid-batch."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    @asynccontextmanager
    async def batch(self) -> AsyncIterator[WaitlistRepository]:
        async with self._session_maker() as session, session.begin():
            yield WaitlistRepository(session)

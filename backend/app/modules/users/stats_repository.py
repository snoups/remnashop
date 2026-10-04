from collections.abc import Sequence
from datetime import date, datetime
from typing import Optional, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.user import User
from app.core.enums import Role
from app.modules.users.dto import UserListStatsDto
from app.modules.users.filters import ACTIVE_SUBSCRIPTIONS


class UserStatsRepository:
    """Aggregates over users for the users list, overview and analytics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_stats(
        self,
        *,
        roles: Sequence[Role],
        new_since: datetime,
        previous_since: datetime,
        growth_since: datetime,
    ) -> UserListStatsDto:
        row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count().filter(User.created_at >= new_since),
                    func.count().filter(ACTIVE_SUBSCRIPTIONS > 0),
                    func.count().filter(User.is_blocked.is_(True)),
                    func.count().filter(
                        User.created_at >= previous_since, User.created_at < new_since
                    ),
                    func.count().filter(User.created_at >= growth_since),
                ).where(User.role.in_(roles), User.deleted_at.is_(None))
            )
        ).one()
        return UserListStatsDto(
            total=row[0],
            new=row[1],
            subscribed=row[2],
            blocked=row[3],
            new_previous=row[4],
            total_growth=row[5],
        )

    async def count_by_role(self, role: Role) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).where(User.role == role, User.deleted_at.is_(None))
            )
            or 0
        )

    async def count_new_since(self, cutoff: datetime, role: Role) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).where(User.role == role, User.created_at >= cutoff)
            )
            or 0
        )

    async def earliest_registration(self, role: Role) -> Optional[date]:
        earliest = await self.session.scalar(
            select(func.min(func.date(func.timezone("UTC", User.created_at)))).where(
                User.role == role
            )
        )
        return cast(Optional[date], earliest)

    async def count_registrations_by_day(
        self, since: datetime, role: Role
    ) -> list[tuple[date, int]]:
        day_col = func.date(func.timezone("UTC", User.created_at))
        stmt = (
            select(day_col, func.count())
            .where(User.role == role, User.created_at >= since)
            .group_by(day_col)
            .order_by(day_col)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return list(rows.all())

    async def list_registrations(
        self, start: datetime, end: datetime, role: Role
    ) -> list[tuple[int, datetime]]:
        result = await self.session.execute(
            select(User.id, User.created_at).where(
                User.role == role, User.created_at >= start, User.created_at < end
            )
        )
        return list(result.tuples().all())

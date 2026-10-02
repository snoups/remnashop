from datetime import datetime
from decimal import Decimal

from sqlalchemy import Numeric, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MAX_SQL_IN_PARAMS
from app.core.db.models.subscription import Subscription
from app.core.enums import Currency, SubscriptionStatus
from app.modules.subscriptions.domain import OWNED_STATUSES


class SubscriptionStatsRepository:
    """Aggregates over subscriptions for overview, analytics and backups."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_by_status(self) -> dict[SubscriptionStatus, int]:
        rows = (
            await self.session.execute(
                select(Subscription.status, func.count())
                .where(Subscription.status != SubscriptionStatus.DELETED)
                .group_by(Subscription.status)
            )
        ).tuples()
        return dict(rows.all())

    async def count_expiring_between(self, start: datetime, end: datetime) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(Subscription)
                .where(
                    Subscription.status.in_(OWNED_STATUSES),
                    Subscription.expire_at >= start,
                    Subscription.expire_at < end,
                )
            )
            or 0
        )

    async def count_churn_window(self, window_start: datetime) -> tuple[int, int]:
        row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count().filter(Subscription.status == SubscriptionStatus.ACTIVE),
                )
                .select_from(Subscription)
                .where(
                    Subscription.created_at < window_start,
                    Subscription.status != SubscriptionStatus.DELETED,
                    Subscription.expire_at >= window_start,
                )
            )
        ).one()
        return int(row[0]), int(row[1])

    async def sum_active_mrr_by_currency(self) -> dict[Currency, Decimal]:
        currency_col = Subscription.plan_snapshot["currency"].astext
        price_col = Subscription.plan_snapshot["price_paid"].astext.cast(Numeric)
        duration_col = Subscription.plan_snapshot["duration_days"].astext.cast(Numeric)
        stmt = (
            select(currency_col, func.sum(price_col / duration_col * 30))
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
            .group_by(currency_col)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return {Currency(currency): amount for currency, amount in rows.all()}

    async def list_user_ids_with_trial(self, user_ids: list[int]) -> set[int]:
        if not user_ids:
            return set()
        trial_users: set[int] = set()
        for start in range(0, len(user_ids), MAX_SQL_IN_PARAMS):
            chunk = user_ids[start : start + MAX_SQL_IN_PARAMS]
            stmt = select(Subscription.user_id.distinct()).where(
                Subscription.user_id.in_(chunk),
                Subscription.is_trial.is_(True),
            )
            result = await self.session.execute(stmt)
            trial_users.update(result.scalars().all())
        return trial_users

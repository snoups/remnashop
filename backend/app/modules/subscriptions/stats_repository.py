from datetime import datetime
from decimal import Decimal
from typing import Final, Optional

from sqlalchemy import Integer, Numeric, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MAX_SQL_IN_PARAMS
from app.core.db.models.subscription import Subscription
from app.core.enums import Currency, SubscriptionStatus
from app.modules.subscriptions.domain import OWNED_STATUSES
from app.modules.subscriptions.dto import LiveSubscriptionDto

_DEFAULT_TRIAL_DAYS: Final[int] = 7
_PAYING_STATUSES: Final[tuple[SubscriptionStatus, ...]] = (
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.LIMITED,
)


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

    async def count_paying(self, *, status: Optional[SubscriptionStatus] = None) -> int:
        statuses = (status,) if status is not None else _PAYING_STATUSES
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(Subscription)
                .where(Subscription.status.in_(statuses), Subscription.is_trial.is_(False))
            )
            or 0
        )

    async def count_active_trials(self) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(Subscription)
                .where(Subscription.status.in_(_PAYING_STATUSES), Subscription.is_trial.is_(True))
            )
            or 0
        )

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

    async def sum_active_mrr_by_currency(self) -> dict[Currency, Decimal]:
        currency_col = Subscription.plan_snapshot["currency"].astext
        price_col = Subscription.plan_snapshot["price_paid"].astext.cast(Numeric)
        duration_col = Subscription.plan_snapshot["duration_days"].astext.cast(Numeric)
        stmt = (
            select(currency_col, func.sum(price_col / duration_col * 30))
            .where(Subscription.status.in_(_PAYING_STATUSES), Subscription.is_trial.is_(False))
            .group_by(currency_col)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return {Currency(currency): amount for currency, amount in rows.all()}

    async def list_user_ids_connected(self, user_ids: list[int]) -> set[int]:
        if not user_ids:
            return set()
        connected: set[int] = set()
        for start in range(0, len(user_ids), MAX_SQL_IN_PARAMS):
            chunk = user_ids[start : start + MAX_SQL_IN_PARAMS]
            stmt = select(Subscription.user_id.distinct()).where(
                Subscription.user_id.in_(chunk),
                Subscription.first_connected_at.is_not(None),
            )
            connected.update((await self.session.execute(stmt)).scalars().all())
        return connected

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

    async def list_trials_started(
        self, start: datetime, end: datetime
    ) -> list[tuple[int, datetime, int]]:
        duration = func.coalesce(
            Subscription.plan_snapshot["duration_days"].astext.cast(Integer), _DEFAULT_TRIAL_DAYS
        )
        stmt = select(Subscription.user_id, Subscription.created_at, duration).where(
            Subscription.is_trial.is_(True),
            Subscription.created_at >= start,
            Subscription.created_at < end,
        )
        return list((await self.session.execute(stmt)).tuples().all())

    async def list_live(self) -> list[LiveSubscriptionDto]:
        snapshot = Subscription.plan_snapshot
        stmt = select(
            Subscription.user_id,
            Subscription.is_trial,
            Subscription.status,
            Subscription.expire_at,
            snapshot["name"].astext,
            snapshot["price_paid"].astext.cast(Numeric),
            snapshot["currency"].astext,
            func.coalesce(snapshot["duration_days"].astext.cast(Integer), 0),
        ).where(Subscription.status.in_(_PAYING_STATUSES))
        rows = (await self.session.execute(stmt)).tuples().all()
        return [
            LiveSubscriptionDto(
                user_id=user_id,
                is_trial=is_trial,
                status=status,
                expire_at=expire_at,
                plan_name=name or "",
                price_paid=price or Decimal(0),
                currency=Currency(currency),
                duration_days=duration,
            )
            for user_id, is_trial, status, expire_at, name, price, currency, duration in rows
        ]

from datetime import datetime
from decimal import Decimal
from typing import Final, Optional

from sqlalchemy import Integer, Numeric, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.filters import in_ids
from app.core.db.models.subscription import Subscription
from app.core.enums import Currency, SubscriptionStatus
from app.modules.subscriptions.domain import OWNED_STATUSES
from app.modules.subscriptions.dto import LiveSubscriptionDto, SubscriptionOverviewCountsDto

_DEFAULT_TRIAL_DAYS: Final[int] = 7
_PAYING_STATUSES: Final[tuple[SubscriptionStatus, ...]] = (
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.LIMITED,
)


class SubscriptionStatsRepository:
    """Aggregates over subscriptions for overview, analytics and backups."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overview_counts(
        self, expiring_from: datetime, expiring_to: datetime
    ) -> SubscriptionOverviewCountsDto:
        status = Subscription.status
        paying = status.in_(_PAYING_STATUSES)
        row = (
            await self.session.execute(
                select(
                    func.count().filter(status == SubscriptionStatus.ACTIVE),
                    func.count().filter(status == SubscriptionStatus.LIMITED),
                    func.count().filter(status == SubscriptionStatus.EXPIRED),
                    func.count().filter(status == SubscriptionStatus.DISABLED),
                    func.count().filter(
                        status.in_(OWNED_STATUSES),
                        Subscription.expire_at >= expiring_from,
                        Subscription.expire_at < expiring_to,
                    ),
                    func.count().filter(
                        status == SubscriptionStatus.ACTIVE, Subscription.is_trial.is_(False)
                    ),
                    func.count().filter(paying, Subscription.is_trial.is_(True)),
                ).where(status != SubscriptionStatus.DELETED)
            )
        ).one()
        return SubscriptionOverviewCountsDto(
            active=row[0],
            limited=row[1],
            expired=row[2],
            disabled=row[3],
            expiring=row[4],
            paid_active=row[5],
            active_trials=row[6],
        )

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

    async def count_expiring_paid(
        self, now: datetime, until: datetime, urgent_until: datetime
    ) -> tuple[int, int]:
        # (expiring before until, of them before urgent_until)
        total, urgent = (
            await self.session.execute(
                select(
                    func.count(), func.count().filter(Subscription.expire_at < urgent_until)
                ).where(
                    Subscription.status.in_(_PAYING_STATUSES),
                    Subscription.is_trial.is_(False),
                    Subscription.expire_at >= now,
                    Subscription.expire_at < until,
                )
            )
        ).one()
        return int(total), int(urgent)

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
        stmt = select(Subscription.user_id.distinct()).where(
            in_ids(Subscription.user_id, user_ids),
            Subscription.first_connected_at.is_not(None),
        )
        connected.update((await self.session.execute(stmt)).scalars().all())
        return connected

    async def list_user_ids_with_trial(self, user_ids: list[int]) -> set[int]:
        if not user_ids:
            return set()
        trial_users: set[int] = set()
        stmt = select(Subscription.user_id.distinct()).where(
            in_ids(Subscription.user_id, user_ids),
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

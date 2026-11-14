from collections.abc import Collection
from datetime import datetime
from decimal import Decimal
from typing import Any, Final, Optional

from sqlalchemy import (
    ARRAY,
    BigInteger,
    ColumnElement,
    DateTime,
    Integer,
    Select,
    Subquery,
    case,
    cast,
    exists,
    func,
    literal,
    or_,
    select,
    tuple_,
)
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.constants import TIME_1D, UNLIMITED_COVERAGE_DAYS
from app.core.db.filters import in_ids
from app.core.db.models.transaction import Transaction
from app.core.db.models.user import User
from app.core.enums import Currency, PaymentGatewayType, PurchaseType, Role, TransactionStatus
from app.modules.transactions.dto import (
    PaidTotalsDto,
    PaidTransactionDto,
    PayerSummaryDto,
    PaymentAttemptDto,
)

_PAID: Final[tuple[ColumnElement[bool], ...]] = (
    Transaction.status == TransactionStatus.PAID,
    Transaction.is_test.is_(False),
)


class TransactionStatsRepository:
    """Aggregates for analytics; updated_at of a PAID row is its paid moment."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _paid_select() -> Select[Any]:
        return select(
            Transaction.user_id,
            Transaction.updated_at,
            Transaction.currency,
            Transaction.final_price,
            Transaction.anchor_final_price,
            Transaction.anchor_base_price,
            Transaction.discount_percent,
            Transaction.discount_promocode_id,
            Transaction.purchase_type,
            Transaction.plan_id,
            Transaction.plan_snapshot["name"].astext,
            Transaction.duration_days,
            Transaction.gateway_type,
            Transaction.plan_discount_percent,
            Transaction.channel,
            Transaction.id,
        ).where(*_PAID)

    def _to_paid(self, row: Any) -> PaidTransactionDto:
        return PaidTransactionDto(
            user_id=row[0],
            paid_at=row[1],
            currency=row[2],
            final_price=row[3],
            anchor_final_price=row[4],
            anchor_base_price=row[5],
            discount_percent=row[6],
            discount_promocode_id=row[7],
            purchase_type=row[8],
            plan_id=row[9],
            plan_name=row[10] or "",
            duration_days=row[11],
            gateway_type=row[12],
            plan_discount_percent=row[13],
            channel=row[14],
            transaction_id=row[15],
        )

    async def list_paid(self, start: Optional[datetime], end: datetime) -> list[PaidTransactionDto]:
        stmt = self._paid_select().where(Transaction.updated_at < end)
        if start is not None:
            stmt = stmt.where(Transaction.updated_at >= start)
        rows = await self.session.execute(stmt.order_by(Transaction.updated_at, Transaction.id))
        return [self._to_paid(row) for row in rows.all()]

    async def list_recent_paid(
        self, limit: int, *, hide_staff_from: Optional[int] = None
    ) -> list[PaidTransactionDto]:
        stmt = self._paid_select()
        if hide_staff_from is not None:
            # same rule as visible_user: staff rows are hidden, the viewer's own are not
            stmt = stmt.where(
                or_(
                    Transaction.user_id.in_(select(User.id).where(User.role == Role.USER)),
                    Transaction.user_id == hide_staff_from,
                )
            )
        stmt = stmt.order_by(Transaction.updated_at.desc(), Transaction.id.desc()).limit(limit)
        return [self._to_paid(row) for row in (await self.session.execute(stmt)).all()]

    async def list_paid_by_users(
        self, user_ids: list[int], end: datetime
    ) -> list[PaidTransactionDto]:
        stmt = (
            self._paid_select()
            .where(in_ids(Transaction.user_id, user_ids), Transaction.updated_at < end)
            .order_by(Transaction.updated_at, Transaction.id)
        )
        rows = (await self.session.execute(stmt)).all()
        return sorted((self._to_paid(row) for row in rows), key=lambda row: row.paid_at)

    async def list_attempts(self, start: datetime, end: datetime) -> list[PaymentAttemptDto]:
        stmt = select(
            Transaction.gateway_type,
            Transaction.status,
            Transaction.anchor_final_price,
        ).where(
            Transaction.is_test.is_(False),
            Transaction.created_at >= start,
            Transaction.created_at < end,
        )
        return [
            PaymentAttemptDto(gateway_type=g, status=s, anchor_final_price=a)
            for g, s, a in (await self.session.execute(stmt)).tuples().all()
        ]

    async def count_failed_by_gateway(self, since: datetime) -> dict[PaymentGatewayType, int]:
        stmt = (
            select(Transaction.gateway_type, func.count())
            .where(
                Transaction.status == TransactionStatus.FAILED,
                Transaction.is_test.is_(False),
                Transaction.updated_at >= since,
            )
            .group_by(Transaction.gateway_type)
        )
        return dict((await self.session.execute(stmt)).tuples().all())

    async def count_stale_pending(self, created_before: datetime, now: datetime) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(
                    Transaction.status == TransactionStatus.PENDING,
                    Transaction.is_test.is_(False),
                    Transaction.created_at < created_before,
                    Transaction.expires_at > now,
                )
            )
            or 0
        )

    def _paid_coverage(
        self, before: datetime, user_ids: Optional[Collection[int]] = None
    ) -> Subquery:
        """One row per paid order with the end of the coverage it extends.

        An early renewal stacks onto the current coverage, a late one starts
        afresh: end_n = max(end_{n-1}, paid_n) + days_n, which unrolls to
        S_n + max over k <= n of (paid_k - S_{k-1}), S being the running sum of
        days: a running max, so window functions can compute it.
        """
        order = (Transaction.updated_at, Transaction.duration_days, Transaction.id)
        conditions: list[ColumnElement[bool]] = [*_PAID, Transaction.updated_at < before]
        if user_ids is not None:
            conditions.append(in_ids(Transaction.user_id, user_ids))
        # an unlimited order covers for good: the ones after it add nothing, and
        # stacked they'd run past the timestamp range
        earlier = aliased(Transaction)
        conditions.append(
            ~exists().where(
                earlier.user_id == Transaction.user_id,
                earlier.status == TransactionStatus.PAID,
                earlier.is_test.is_(False),
                earlier.duration_days == 0,
                tuple_(earlier.updated_at, earlier.duration_days, earlier.id)
                < tuple_(Transaction.updated_at, Transaction.duration_days, Transaction.id),
            )
        )
        # an unlimited order has 0 days and covers for good
        covered_days = case(
            (Transaction.duration_days == 0, UNLIMITED_COVERAGE_DAYS),
            else_=Transaction.duration_days,
        )
        days_before = func.coalesce(
            func.sum(covered_days).over(
                partition_by=Transaction.user_id, order_by=order, rows=(None, -1)
            ),
            0,
        )
        steps = (
            select(
                Transaction.user_id,
                Transaction.updated_at.label("paid_at"),
                covered_days.label("days"),
                Transaction.duration_days.label("paid_days"),
                Transaction.id,
                days_before.label("days_before"),
            )
            .where(*conditions)
            .subquery()
        )
        # ties broken as the running sum above orders them, by the days paid for
        step_order = (steps.c.paid_at, steps.c.paid_days, steps.c.id)
        ends = select(
            steps.c.user_id,
            steps.c.paid_at,
            steps.c.paid_days,
            steps.c.id,
            (
                func.max(steps.c.paid_at - _days(steps.c.days_before)).over(
                    partition_by=steps.c.user_id, order_by=step_order, rows=(None, 0)
                )
                + _days(steps.c.days_before + steps.c.days)
            ).label("covered_until"),
        ).subquery()
        return select(
            ends.c.user_id,
            ends.c.paid_at,
            ends.c.covered_until,
            func.lag(ends.c.covered_until)
            .over(
                partition_by=ends.c.user_id,
                order_by=(ends.c.paid_at, ends.c.paid_days, ends.c.id),
            )
            .label("previous_until"),
        ).subquery()

    async def users_covered_at(
        self, points: Collection[datetime], before: datetime
    ) -> dict[datetime, set[int]]:
        """For each point, the users whose coverage from orders paid before `before` includes it."""
        covered: dict[datetime, set[int]] = {point: set() for point in points}
        if not covered:
            return covered
        coverage = self._paid_coverage(before)
        probes = select(
            func.unnest(literal(list(covered), ARRAY(DateTime(timezone=True)))).label("at")
        ).subquery()
        stmt = (
            select(probes.c.at, coverage.c.user_id)
            .distinct()
            .join(
                coverage,
                (coverage.c.paid_at <= probes.c.at) & (coverage.c.covered_until > probes.c.at),
            )
        )
        for at, user_id in (await self.session.execute(stmt)).tuples():
            covered[at].add(user_id)
        return covered

    async def users_covered_at_their_points(
        self, points: dict[int, datetime], before: datetime
    ) -> set[int]:
        """Of the users in `points`, those covered at their own moment."""
        if not points:
            return set()
        coverage = self._paid_coverage(before, points.keys())
        probes = select(
            func.unnest(literal(list(points), ARRAY(BigInteger))).label("user_id"),
            func.unnest(literal(list(points.values()), ARRAY(DateTime(timezone=True)))).label("at"),
        ).subquery()
        stmt = (
            select(probes.c.user_id.distinct())
            .join(coverage, coverage.c.user_id == probes.c.user_id)
            .where(coverage.c.paid_at <= probes.c.at, coverage.c.covered_until > probes.c.at)
        )
        return set((await self.session.scalars(stmt)).all())

    async def total_covered_days(self, now: datetime) -> tuple[int, float]:
        """(payers, days of paid coverage up to now, summed over them)."""
        coverage = self._paid_coverage(now)
        start = func.least(
            func.greatest(
                coverage.c.paid_at, func.coalesce(coverage.c.previous_until, coverage.c.paid_at)
            ),
            now,
        )
        added = func.greatest(
            func.extract("epoch", func.least(coverage.c.covered_until, now) - start), 0
        )
        payers, seconds = (
            await self.session.execute(
                select(func.count(coverage.c.user_id.distinct()), func.coalesce(func.sum(added), 0))
            )
        ).one()
        return int(payers), float(seconds) / TIME_1D

    async def first_paid_at(
        self,
        before: datetime,
        *,
        since: Optional[datetime] = None,
        user_ids: Optional[Collection[int]] = None,
    ) -> dict[int, datetime]:
        """Each payer's first paid moment before `before`; with `since`, only
        payers whose first payment is at or after it."""
        first = func.min(Transaction.updated_at)
        stmt = (
            select(Transaction.user_id, first)
            .where(*_PAID, Transaction.updated_at < before)
            .group_by(Transaction.user_id)
        )
        if since is not None:
            stmt = stmt.having(first >= since)
        if user_ids is not None:
            if not user_ids:
                return {}
            stmt = stmt.where(in_ids(Transaction.user_id, user_ids))
        return dict((await self.session.execute(stmt)).tuples().all())

    async def paid_totals(self, start: datetime, end: datetime) -> PaidTotalsDto:
        payments, paying_users, revenue = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count(Transaction.user_id.distinct()),
                    func.coalesce(func.sum(Transaction.anchor_final_price), 0),
                ).where(*_PAID, Transaction.updated_at >= start, Transaction.updated_at < end)
            )
        ).one()
        return PaidTotalsDto(payments=payments, paying_users=paying_users, revenue=revenue)

    async def revenue_by_currency(self, start: datetime, end: datetime) -> dict[Currency, Decimal]:
        stmt = (
            select(Transaction.currency, func.sum(Transaction.final_price))
            .where(*_PAID, Transaction.updated_at >= start, Transaction.updated_at < end)
            .group_by(Transaction.currency)
        )
        return dict((await self.session.execute(stmt)).tuples().all())

    async def payer_summaries(
        self, before: datetime, user_ids: Optional[Collection[int]] = None
    ) -> list[PayerSummaryDto]:
        conditions: list[ColumnElement[bool]] = [*_PAID, Transaction.updated_at < before]
        if user_ids is not None:
            if not user_ids:
                return []
            conditions.append(in_ids(Transaction.user_id, user_ids))
        order = (Transaction.updated_at, Transaction.id)
        first_plan = func.coalesce(
            func.array_agg(aggregate_order_by(Transaction.plan_snapshot["name"].astext, *order))[1],
            "",
        )
        stmt = (
            select(
                Transaction.user_id,
                func.count(),
                func.count().filter(Transaction.purchase_type == PurchaseType.RENEW),
                func.sum(Transaction.anchor_final_price),
                func.min(Transaction.updated_at),
                func.max(Transaction.updated_at),
                first_plan,
            )
            .where(*conditions)
            .group_by(Transaction.user_id)
        )
        return [
            PayerSummaryDto(
                user_id=row[0],
                payments=row[1],
                renewals=row[2],
                spent=row[3],
                first_paid_at=row[4],
                last_paid_at=row[5],
                first_plan_name=row[6],
            )
            for row in (await self.session.execute(stmt)).all()
        ]


def _days(count: ColumnElement[Any]) -> ColumnElement[Any]:
    # a running sum of days is bigint; make_interval takes int
    return func.make_interval(0, 0, 0, cast(count, Integer))

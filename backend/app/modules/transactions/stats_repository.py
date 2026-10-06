from datetime import datetime
from typing import Any, Final, Optional

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MAX_SQL_IN_PARAMS
from app.core.db.models.transaction import Transaction
from app.core.enums import PaymentGatewayType, TransactionStatus
from app.modules.transactions.dto import PaidTransactionDto, PaymentAttemptDto

_PAID: Final[tuple[ColumnElement[bool], ...]] = (
    Transaction.status == TransactionStatus.PAID,
    Transaction.is_test.is_(False),
)


class TransactionStatsRepository:
    """Row lists for analytics; updated_at of a PAID row is its paid moment."""

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
        ).where(*_PAID)

    @staticmethod
    def _to_paid(row: Any) -> PaidTransactionDto:
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
        )

    async def list_paid(self, start: Optional[datetime], end: datetime) -> list[PaidTransactionDto]:
        stmt = self._paid_select().where(Transaction.updated_at < end)
        if start is not None:
            stmt = stmt.where(Transaction.updated_at >= start)
        rows = await self.session.execute(stmt.order_by(Transaction.updated_at, Transaction.id))
        return [self._to_paid(row) for row in rows.all()]

    async def list_recent_paid(self, limit: int) -> list[PaidTransactionDto]:
        stmt = (
            self._paid_select()
            .order_by(Transaction.updated_at.desc(), Transaction.id.desc())
            .limit(limit)
        )
        return [self._to_paid(row) for row in (await self.session.execute(stmt)).all()]

    async def list_paid_by_users(
        self, user_ids: list[int], end: datetime
    ) -> list[PaidTransactionDto]:
        result: list[PaidTransactionDto] = []
        for start in range(0, len(user_ids), MAX_SQL_IN_PARAMS):
            chunk = user_ids[start : start + MAX_SQL_IN_PARAMS]
            stmt = (
                self._paid_select()
                .where(Transaction.user_id.in_(chunk), Transaction.updated_at < end)
                .order_by(Transaction.updated_at, Transaction.id)
            )
            result.extend(self._to_paid(row) for row in (await self.session.execute(stmt)).all())
        return sorted(result, key=lambda row: row.paid_at)

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

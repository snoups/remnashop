from datetime import date, datetime
from decimal import Decimal
from typing import Final, Optional, cast

from sqlalchemy import ColumnElement, CursorResult, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import INT32_MAX, MAX_SQL_IN_PARAMS
from app.core.db.models.transaction import Transaction
from app.core.db.timestamp import NOW_FUNC
from app.core.enums import Currency, PaymentGatewayType, PurchaseType, TransactionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.modules.subscriptions import PlanSnapshot
from app.modules.transactions.dto import DEFAULT_PAGE_SIZE, CreateTransactionDto, TransactionDto

# Test orders never provision a subscription and must stay out of every
# revenue/analytics/reconciliation query, and out of the admin order list.
_NOT_TEST: Final[ColumnElement[bool]] = Transaction.is_test.is_(False)


def _order_filters(
    *,
    status: Optional[TransactionStatus] = None,
    gateway_type: Optional[PaymentGatewayType] = None,
    purchase_type: Optional[PurchaseType] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    search: Optional[str] = None,
    user_id: Optional[int] = None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [_NOT_TEST]
    if user_id is not None:
        filters.append(Transaction.user_id == user_id)
    if status is not None:
        filters.append(Transaction.status == status)
    if gateway_type is not None:
        filters.append(Transaction.gateway_type == gateway_type)
    if purchase_type is not None:
        filters.append(Transaction.purchase_type == purchase_type)
    if created_from is not None:
        filters.append(Transaction.created_at >= created_from)
    if created_to is not None:
        filters.append(Transaction.created_at < created_to)
    if search:
        pattern = f"%{search}%"
        search_filters: list[ColumnElement[bool]] = [
            Transaction.external_payment_id.ilike(pattern),
            Transaction.customer_email.ilike(pattern),
            Transaction.plan_snapshot["name"].astext.ilike(pattern),
        ]
        # id/user_id are Integer; a longer digit string would overflow asyncpg
        if search.isdigit() and int(search) <= INT32_MAX:
            search_filters += [
                Transaction.id == int(search),
                Transaction.user_id == int(search),
            ]
        filters.append(or_(*search_filters))
    return filters


class TransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: Transaction) -> TransactionDto:
        return TransactionDto(
            id=row.id,
            user_id=row.user_id,
            plan_id=row.plan_id,
            plan_snapshot=PlanSnapshot.from_json(dict(row.plan_snapshot)),
            duration_days=row.duration_days,
            currency=row.currency,
            purchase_type=row.purchase_type,
            target_subscription_id=row.target_subscription_id,
            gateway_type=row.gateway_type,
            external_payment_id=row.external_payment_id,
            status=row.status,
            base_price=row.base_price,
            discount_percent=row.discount_percent,
            discount_source=row.discount_source,
            final_price=row.final_price,
            discount_promocode_id=row.discount_promocode_id,
            customer_email=row.customer_email,
            idempotency_key=row.idempotency_key,
            expires_at=row.expires_at,
            is_test=row.is_test,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def create(self, data: CreateTransactionDto) -> TransactionDto:
        row = Transaction(
            user_id=data.user_id,
            plan_id=data.plan_id,
            plan_snapshot=data.plan_snapshot.to_json(),
            duration_days=data.duration_days,
            currency=data.currency,
            purchase_type=data.purchase_type,
            target_subscription_id=data.target_subscription_id,
            gateway_type=data.gateway_type,
            base_price=data.base_price,
            discount_percent=data.discount_percent,
            discount_source=data.discount_source,
            final_price=data.final_price,
            discount_promocode_id=data.discount_promocode_id,
            customer_email=data.customer_email,
            idempotency_key=data.idempotency_key,
            expires_at=data.expires_at,
            is_test=data.is_test,
        )
        self.session.add(row)
        await self.session.flush()
        return self._to_dto(row)

    async def get_by_id(self, order_id: int) -> TransactionDto:
        row = await self.session.get(Transaction, order_id)
        if row is None:
            raise NotFoundError(
                f"Transaction '{order_id}' not found", code=ErrorCode.PAYMENT_ORDER_NOT_FOUND
            )
        return self._to_dto(row)

    async def get_by_idempotency_key(
        self, key: str, *, gateway_type: Optional[PaymentGatewayType] = None
    ) -> Optional[TransactionDto]:
        filters = [Transaction.idempotency_key == key]
        if gateway_type is not None:
            filters.append(Transaction.gateway_type == gateway_type)
        row = await self.session.scalar(select(Transaction).where(*filters))
        return self._to_dto(row) if row is not None else None

    async def get_by_external_payment_id(
        self, external_id: str, *, gateway_type: Optional[PaymentGatewayType] = None
    ) -> Optional[TransactionDto]:
        # external_payment_id is unique per gateway only; two providers can
        # issue the same id
        filters = [Transaction.external_payment_id == external_id]
        if gateway_type is not None:
            filters.append(Transaction.gateway_type == gateway_type)
        row = await self.session.scalar(select(Transaction).where(*filters))
        return self._to_dto(row) if row is not None else None

    async def mark_status(
        self,
        order_id: int,
        status: TransactionStatus,
        *,
        external_payment_id: Optional[str] = None,
    ) -> TransactionDto:
        row = await self.session.get(Transaction, order_id)
        if row is None:
            raise NotFoundError(
                f"Transaction '{order_id}' not found", code=ErrorCode.PAYMENT_ORDER_NOT_FOUND
            )
        row.status = status
        if external_payment_id is not None:
            row.external_payment_id = external_payment_id
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def mark_status_if(
        self,
        order_id: int,
        status: TransactionStatus,
        *,
        current: frozenset[TransactionStatus],
    ) -> bool:
        # conditional in SQL so a status that landed meanwhile (e.g. PAID) wins
        result = await self.session.execute(
            update(Transaction)
            .where(Transaction.id == order_id, Transaction.status.in_(current))
            .values(status=status, updated_at=NOW_FUNC)
        )
        return cast(CursorResult, result).rowcount > 0

    async def cancel_expired_pending(self, cutoff: datetime) -> list[TransactionDto]:
        # a Core update() skips the ORM's onupdate, so updated_at is set by hand
        rows = await self.session.scalars(
            update(Transaction)
            .where(
                Transaction.status == TransactionStatus.PENDING,
                Transaction.expires_at <= cutoff,
            )
            .values(status=TransactionStatus.CANCELED, updated_at=NOW_FUNC)
            .returning(Transaction)
        )
        return [self._to_dto(row) for row in rows.all()]

    async def list_paid_awaiting_reconciliation(
        self, cutoff: datetime, *, since: datetime
    ) -> list[TransactionDto]:
        rows = (
            await self.session.scalars(
                select(Transaction).where(
                    Transaction.status == TransactionStatus.PAID,
                    _NOT_TEST,
                    Transaction.fulfilled_at.is_(None),
                    Transaction.updated_at <= cutoff,
                    Transaction.updated_at >= since,
                )
            )
        ).all()
        return [self._to_dto(row) for row in rows]

    async def mark_fulfilled(self, order_id: int) -> None:
        # updated_at is the paid-at timestamp every revenue query groups by --
        # pinned to itself, since Core update() still applies its onupdate.
        await self.session.execute(
            update(Transaction)
            .where(Transaction.id == order_id, Transaction.fulfilled_at.is_(None))
            .values(fulfilled_at=NOW_FUNC, updated_at=Transaction.updated_at)
        )

    async def list_paginated(
        self,
        *,
        status: Optional[TransactionStatus] = None,
        gateway_type: Optional[PaymentGatewayType] = None,
        purchase_type: Optional[PurchaseType] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[TransactionDto], int]:
        filters = _order_filters(
            status=status,
            gateway_type=gateway_type,
            purchase_type=purchase_type,
            created_from=created_from,
            created_to=created_to,
            search=search,
            user_id=user_id,
        )

        count_stmt = select(func.count()).select_from(Transaction).where(*filters)
        total = await self.session.scalar(count_stmt)

        stmt = (
            select(Transaction)
            .where(*filters)
            .order_by(Transaction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()
        return [self._to_dto(row) for row in rows], int(total or 0)

    async def summarize(
        self,
        *,
        status: Optional[TransactionStatus] = None,
        gateway_type: Optional[PaymentGatewayType] = None,
        purchase_type: Optional[PurchaseType] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> list[tuple[TransactionStatus, Currency, int, Decimal, Decimal]]:
        filters = _order_filters(
            status=status,
            gateway_type=gateway_type,
            purchase_type=purchase_type,
            created_from=created_from,
            created_to=created_to,
            search=search,
            user_id=user_id,
        )
        stmt = (
            select(
                Transaction.status,
                Transaction.currency,
                func.count(),
                func.sum(Transaction.final_price),
                func.sum(Transaction.base_price),
            )
            .where(*filters)
            .group_by(Transaction.status, Transaction.currency)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return list(rows.all())

    async def list_gateway_types(self) -> list[PaymentGatewayType]:
        rows = await self.session.scalars(
            select(Transaction.gateway_type)
            .where(_NOT_TEST)
            .distinct()
            .order_by(Transaction.gateway_type)
        )
        return list(rows)

    async def sum_paid_final_price_by_user_ids(
        self, user_ids: list[int]
    ) -> dict[Currency, Decimal]:
        if not user_ids:
            return {}
        totals: dict[Currency, Decimal] = {}
        for start in range(0, len(user_ids), MAX_SQL_IN_PARAMS):
            chunk = user_ids[start : start + MAX_SQL_IN_PARAMS]
            stmt = (
                select(Transaction.currency, func.sum(Transaction.final_price))
                .where(
                    Transaction.user_id.in_(chunk),
                    Transaction.status == TransactionStatus.PAID,
                    _NOT_TEST,
                )
                .group_by(Transaction.currency)
            )
            rows = (await self.session.execute(stmt)).tuples()
            for currency, amount in rows.all():
                totals[currency] = totals.get(currency, Decimal(0)) + amount
        return totals

    async def sum_paid_promocode_discounts(self) -> tuple[int, dict[Currency, Decimal]]:
        # (paid orders, discount amount per currency)
        stmt = (
            select(
                Transaction.currency,
                func.count(),
                func.sum(Transaction.base_price - Transaction.final_price),
            )
            .where(
                Transaction.status == TransactionStatus.PAID,
                Transaction.discount_promocode_id.is_not(None),
                _NOT_TEST,
            )
            .group_by(Transaction.currency)
        )
        count = 0
        totals: dict[Currency, Decimal] = {}
        for currency, orders, amount in (await self.session.execute(stmt)).tuples():
            count += orders
            totals[currency] = amount
        return count, totals

    async def list_user_ids_with_paid_order(self, user_ids: list[int]) -> set[int]:
        if not user_ids:
            return set()
        paid: set[int] = set()
        for start in range(0, len(user_ids), MAX_SQL_IN_PARAMS):
            chunk = user_ids[start : start + MAX_SQL_IN_PARAMS]
            stmt = select(Transaction.user_id.distinct()).where(
                Transaction.user_id.in_(chunk),
                Transaction.status == TransactionStatus.PAID,
                _NOT_TEST,
            )
            result = await self.session.execute(stmt)
            paid.update(result.scalars().all())
        return paid

    async def list_user_ids_with_multiple_paid_orders(self, user_ids: list[int]) -> set[int]:
        if not user_ids:
            return set()
        repeat_payers: set[int] = set()
        for start in range(0, len(user_ids), MAX_SQL_IN_PARAMS):
            chunk = user_ids[start : start + MAX_SQL_IN_PARAMS]
            stmt = (
                select(Transaction.user_id)
                .where(
                    Transaction.user_id.in_(chunk),
                    Transaction.status == TransactionStatus.PAID,
                    _NOT_TEST,
                )
                .group_by(Transaction.user_id)
                .having(func.count() > 1)
            )
            result = await self.session.execute(stmt)
            repeat_payers.update(result.scalars().all())
        return repeat_payers

    async def list_paid_user_month_pairs(
        self, user_ids: list[int], since: datetime
    ) -> list[tuple[int, date]]:
        if not user_ids:
            return []
        month_col = func.date(
            func.date_trunc("month", func.timezone("UTC", Transaction.updated_at))
        )
        pairs: list[tuple[int, date]] = []
        for start in range(0, len(user_ids), MAX_SQL_IN_PARAMS):
            chunk = user_ids[start : start + MAX_SQL_IN_PARAMS]
            stmt = (
                select(Transaction.user_id, month_col)
                .where(
                    Transaction.user_id.in_(chunk),
                    Transaction.status == TransactionStatus.PAID,
                    _NOT_TEST,
                    Transaction.updated_at >= since,
                )
                .distinct()
            )
            result = await self.session.execute(stmt)
            pairs.extend(result.tuples().all())
        return pairs

    async def sum_paid_final_price_per_user(
        self, user_ids: Optional[list[int]] = None, *, created_before: Optional[datetime] = None
    ) -> dict[int, dict[Currency, Decimal]]:
        stmt = (
            select(Transaction.user_id, Transaction.currency, func.sum(Transaction.final_price))
            .where(Transaction.status == TransactionStatus.PAID, _NOT_TEST)
            .group_by(Transaction.user_id, Transaction.currency)
        )
        if user_ids is not None:
            stmt = stmt.where(Transaction.user_id.in_(user_ids))
        if created_before is not None:
            stmt = stmt.where(Transaction.created_at < created_before)
        rows = (await self.session.execute(stmt)).tuples()
        totals: dict[int, dict[Currency, Decimal]] = {}
        for user_id, currency, amount in rows.all():
            totals.setdefault(user_id, {})[currency] = amount
        return totals

    async def count_paid_since(self, since: datetime) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).where(
                    Transaction.status == TransactionStatus.PAID,
                    _NOT_TEST,
                    Transaction.updated_at >= since,
                )
            )
            or 0
        )

    async def sum_paid_final_price_since(self, since: datetime) -> dict[Currency, Decimal]:
        stmt = (
            select(Transaction.currency, func.sum(Transaction.final_price))
            .where(
                Transaction.status == TransactionStatus.PAID,
                _NOT_TEST,
                Transaction.updated_at >= since,
            )
            .group_by(Transaction.currency)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return dict(rows.all())

    async def daily_paid_revenue_by_currency(
        self, since: datetime
    ) -> dict[date, dict[Currency, Decimal]]:
        day_col = func.date(func.timezone("UTC", Transaction.updated_at))
        stmt = (
            select(day_col, Transaction.currency, func.sum(Transaction.final_price))
            .where(
                Transaction.status == TransactionStatus.PAID,
                _NOT_TEST,
                Transaction.updated_at >= since,
            )
            .group_by(day_col, Transaction.currency)
            .order_by(day_col)
        )
        rows = (await self.session.execute(stmt)).tuples()
        result: dict[date, dict[Currency, Decimal]] = {}
        for day, currency, amount in rows.all():
            result.setdefault(day, {})[currency] = amount
        return result

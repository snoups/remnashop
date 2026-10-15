from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Final, Optional, cast

from sqlalchemy import ColumnElement, CursorResult, and_, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_PAGE_SIZE, INT32_MAX
from app.core.db.filters import in_ids
from app.core.db.models.subscription_purchase_idempotency import SubscriptionPurchaseIdempotency
from app.core.db.models.transaction import Transaction
from app.core.db.models.user import User
from app.core.db.timestamp import NOW_FUNC
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseType,
    Role,
    TransactionStatus,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import SpentPurchaseDiscount
from app.modules.subscriptions import IDEMPOTENCY_KEY_RETENTION_DAYS, PlanSnapshot
from app.modules.transactions.dto import CreateTransactionDto, TransactionDto

# Test orders never provision a subscription and must stay out of every
# revenue/analytics/reconciliation query, and out of the admin order list.
_NOT_TEST: Final[ColumnElement[bool]] = Transaction.is_test.is_(False)

# Must stay inside the idempotency-key retention: past it, a key-less order
# looks unprovisioned and a redispatch would provision it a second time.
RECONCILE_WINDOW: Final[timedelta] = timedelta(days=IDEMPOTENCY_KEY_RETENTION_DAYS - 1)


def _order_filters(
    *,
    status: Optional[TransactionStatus] = None,
    gateway_type: Optional[PaymentGatewayType] = None,
    purchase_type: Optional[PurchaseType] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    search: Optional[str] = None,
    user_id: Optional[int] = None,
    search_staff: bool = True,
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
        email_match: ColumnElement[bool] = Transaction.customer_email.ilike(pattern)
        if not search_staff:
            # a staff order's email is hidden from this caller; matching it would be an oracle
            email_match = and_(
                email_match,
                Transaction.user_id.in_(select(User.id).where(User.role == Role.USER)),
            )
        search_filters: list[ColumnElement[bool]] = [
            Transaction.external_payment_id.ilike(pattern),
            email_match,
            Transaction.plan_snapshot["name"].astext.ilike(pattern),
        ]
        # id/user_id are Integer; a longer digit string would overflow asyncpg
        if search.isascii() and search.isdigit() and int(search) <= INT32_MAX:
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
            plan_discount_percent=row.plan_discount_percent,
            discount_source=row.discount_source,
            final_price=row.final_price,
            anchor_base_price=row.anchor_base_price,
            anchor_final_price=row.anchor_final_price,
            discount_promocode_id=row.discount_promocode_id,
            discount_from_promocode=row.discount_from_promocode,
            customer_email=row.customer_email,
            idempotency_key=row.idempotency_key,
            expires_at=row.expires_at,
            fulfilled_at=row.fulfilled_at,
            fulfilled_subscription_id=row.fulfilled_subscription_id,
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
            plan_discount_percent=data.plan_discount_percent,
            discount_source=data.discount_source,
            final_price=data.final_price,
            anchor_base_price=data.anchor_base_price,
            anchor_final_price=data.anchor_final_price,
            discount_promocode_id=data.discount_promocode_id,
            discount_from_promocode=data.discount_from_promocode,
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

    async def get_by_id_for_update(self, order_id: int) -> TransactionDto:
        row = await self.session.get(
            Transaction, order_id, with_for_update=True, populate_existing=True
        )
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
        external_payment_id: Optional[str] = None,
    ) -> bool:
        # conditional in SQL so a status that landed meanwhile (e.g. PAID) wins
        values: dict[str, Any] = {"status": status, "updated_at": NOW_FUNC}
        if external_payment_id is not None:
            values["external_payment_id"] = external_payment_id
        result = await self.session.execute(
            update(Transaction)
            .where(Transaction.id == order_id, Transaction.status.in_(current))
            .values(**values)
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

    async def mark_fulfilled(self, order_id: int, subscription_id: int) -> None:
        # updated_at is the paid-at timestamp every revenue query groups by --
        # pinned to itself, since Core update() still applies its onupdate.
        await self.session.execute(
            update(Transaction)
            .where(Transaction.id == order_id, Transaction.fulfilled_at.is_(None))
            .values(
                fulfilled_at=NOW_FUNC,
                fulfilled_subscription_id=subscription_id,
                updated_at=Transaction.updated_at,
            )
        )

    async def lock_status_by_idempotency_key(self, key: str) -> Optional[TransactionStatus]:
        # serializes with a refund's status write, so a reward can't land after it
        status: Optional[TransactionStatus] = await self.session.scalar(
            select(Transaction.status).where(Transaction.idempotency_key == key).with_for_update()
        )
        return status

    async def count_open_new_orders(
        self, user_id: int, now: datetime, *, exclude_key: Optional[str] = None
    ) -> int:
        conditions = [
            _NOT_TEST,
            Transaction.user_id == user_id,
            Transaction.purchase_type == PurchaseType.NEW,
        ]
        if exclude_key is not None:
            conditions.append(Transaction.idempotency_key != exclude_key)
        count = await self.session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(
                *conditions,
                or_(
                    and_(
                        Transaction.status == TransactionStatus.PENDING,
                        Transaction.expires_at > now,
                    ),
                    and_(
                        Transaction.status == TransactionStatus.PAID,
                        Transaction.fulfilled_subscription_id.is_(None),
                        # older paid orders are past reconcile and no longer turn
                        # into a subscription on their own
                        Transaction.updated_at >= now - RECONCILE_WINDOW,
                        # provisioned but not yet linked by the reconcile sweep
                        ~exists().where(
                            SubscriptionPurchaseIdempotency.key == Transaction.idempotency_key,
                            SubscriptionPurchaseIdempotency.subscription_id.is_not(None),
                        ),
                    ),
                ),
            )
        )
        return count or 0

    async def fail_unpaid_free_order(self, idempotency_key: str) -> Optional[SpentPurchaseDiscount]:
        row = await self.session.execute(
            update(Transaction)
            .where(
                Transaction.idempotency_key == idempotency_key,
                Transaction.status == TransactionStatus.PAID,
                Transaction.final_price == 0,
                Transaction.fulfilled_subscription_id.is_(None),
            )
            .values(status=TransactionStatus.FAILED, updated_at=NOW_FUNC)
            .returning(
                Transaction.user_id,
                Transaction.discount_source,
                Transaction.discount_percent,
                Transaction.discount_promocode_id,
                Transaction.discount_from_promocode,
            )
        )
        failed = row.first()
        if failed is None or failed.discount_source is not DiscountSource.PURCHASE:
            return None
        return SpentPurchaseDiscount(
            user_id=failed.user_id,
            percent=failed.discount_percent,
            promocode_id=failed.discount_promocode_id,
            from_promocode=failed.discount_from_promocode,
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
        search_staff: bool = True,
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
            search_staff=search_staff,
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
        search_staff: bool = True,
    ) -> list[tuple[TransactionStatus, int, Decimal, Decimal]]:
        filters = _order_filters(
            status=status,
            gateway_type=gateway_type,
            purchase_type=purchase_type,
            created_from=created_from,
            created_to=created_to,
            search=search,
            user_id=user_id,
            search_staff=search_staff,
        )
        stmt = (
            select(
                Transaction.status,
                func.count(),
                func.sum(Transaction.anchor_final_price),
                func.sum(Transaction.anchor_base_price),
            )
            .where(*filters)
            .group_by(Transaction.status)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return list(rows.all())

    async def rescale_anchor_amounts(self, factor: Decimal) -> None:
        await self.session.execute(
            update(Transaction).values(
                anchor_base_price=func.round(Transaction.anchor_base_price * factor, 2),
                anchor_final_price=func.round(Transaction.anchor_final_price * factor, 2),
                # paid-at timestamp, pinned like mark_fulfilled does
                updated_at=Transaction.updated_at,
            )
        )

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
        stmt = (
            select(Transaction.currency, func.sum(Transaction.final_price))
            .where(
                in_ids(Transaction.user_id, user_ids),
                Transaction.status == TransactionStatus.PAID,
                _NOT_TEST,
            )
            .group_by(Transaction.currency)
        )
        rows = (await self.session.execute(stmt)).tuples()
        for currency, amount in rows.all():
            totals[currency] = totals.get(currency, Decimal(0)) + amount
        return totals

    async def sum_paid_anchor_amount_by_user_ids(self, user_ids: list[int]) -> Decimal:
        total = await self.session.scalar(
            select(func.sum(Transaction.anchor_final_price)).where(
                in_ids(Transaction.user_id, user_ids),
                Transaction.status == TransactionStatus.PAID,
                _NOT_TEST,
            )
        )
        return total or Decimal(0)

    async def sum_paid_promocode_discounts(self) -> tuple[int, Decimal]:
        # (paid orders, discount amount in the anchor currency)
        stmt = select(
            func.count(),
            # the plan's own discount isn't the promocode's
            func.sum(
                Transaction.anchor_base_price * (100 - Transaction.plan_discount_percent) / 100
                - Transaction.anchor_final_price
            ),
        ).where(
            Transaction.status == TransactionStatus.PAID,
            Transaction.discount_promocode_id.is_not(None),
            _NOT_TEST,
        )
        count, amount = (await self.session.execute(stmt)).tuples().one()
        return count, amount or Decimal(0)

    async def list_user_ids_with_paid_order(self, user_ids: list[int]) -> set[int]:
        if not user_ids:
            return set()
        paid: set[int] = set()
        stmt = select(Transaction.user_id.distinct()).where(
            in_ids(Transaction.user_id, user_ids),
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
        stmt = (
            select(Transaction.user_id)
            .where(
                in_ids(Transaction.user_id, user_ids),
                Transaction.status == TransactionStatus.PAID,
                _NOT_TEST,
            )
            .group_by(Transaction.user_id)
            .having(func.count() > 1)
        )
        result = await self.session.execute(stmt)
        repeat_payers.update(result.scalars().all())
        return repeat_payers

    async def sum_paid_anchor_amount_per_user(
        self,
        user_ids: Optional[list[int]] = None,
        *,
        created_before: Optional[datetime] = None,
        paid_since: Optional[datetime] = None,
    ) -> dict[int, Decimal]:
        stmt = (
            select(Transaction.user_id, func.sum(Transaction.anchor_final_price))
            .where(Transaction.status == TransactionStatus.PAID, _NOT_TEST)
            .group_by(Transaction.user_id)
        )
        if user_ids is not None:
            stmt = stmt.where(Transaction.user_id.in_(user_ids))
        if created_before is not None:
            stmt = stmt.where(Transaction.created_at < created_before)
        if paid_since is not None:
            # updated_at of a PAID row is its paid moment
            stmt = stmt.where(Transaction.updated_at >= paid_since)
        return dict((await self.session.execute(stmt)).tuples().all())

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

    async def list_paid_periods(self, user_ids: list[int]) -> list[tuple[int, datetime, int]]:
        periods: list[tuple[int, datetime, int]] = []
        stmt = (
            select(Transaction.user_id, Transaction.updated_at, Transaction.duration_days)
            .where(
                in_ids(Transaction.user_id, user_ids),
                Transaction.status == TransactionStatus.PAID,
                _NOT_TEST,
            )
            .order_by(Transaction.user_id, Transaction.updated_at)
        )
        periods.extend((await self.session.execute(stmt)).tuples().all())
        return periods

    async def first_paid_at_since(self, since: datetime) -> dict[int, datetime]:
        first_paid = func.min(Transaction.updated_at)
        stmt = (
            select(Transaction.user_id, first_paid)
            .where(Transaction.status == TransactionStatus.PAID, _NOT_TEST)
            .group_by(Transaction.user_id)
            .having(first_paid >= since)
        )
        return dict((await self.session.execute(stmt)).tuples().all())

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

    async def daily_paid_anchor_revenue(self, since: datetime) -> dict[date, Decimal]:
        day_col = func.date(func.timezone("UTC", Transaction.updated_at))
        stmt = (
            select(day_col, func.sum(Transaction.anchor_final_price))
            .where(
                Transaction.status == TransactionStatus.PAID,
                _NOT_TEST,
                Transaction.updated_at >= since,
            )
            .group_by(day_col)
            .order_by(day_col)
        )
        return dict((await self.session.execute(stmt)).tuples().all())

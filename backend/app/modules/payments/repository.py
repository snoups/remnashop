from datetime import date, datetime
from decimal import Decimal
from typing import Final, Optional, cast

from sqlalchemy import ColumnElement, CursorResult, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import INT32_MAX
from app.core.db.models.payment_order import PaymentOrder
from app.core.db.timestamp import NOW_FUNC
from app.core.enums import Currency, PaymentGatewayType, PaymentOrderStatus, PurchaseType
from app.core.exceptions import NotFoundError
from app.modules.payments.dto import DEFAULT_PAGE_SIZE, CreatePaymentOrderDto, PaymentOrderDto
from app.modules.subscriptions import PlanSnapshot

# asyncpg caps a statement at 32,767 bind parameters; stay well under that so a
# large attributed-user list still fits after other predicates are added.
_MAX_IN_PARAMS: Final[int] = 20_000

# Test orders never provision a subscription and must stay out of every
# revenue/analytics/reconciliation query, and out of the admin order list.
_NOT_TEST: Final[ColumnElement[bool]] = PaymentOrder.is_test.is_(False)


def _order_filters(
    *,
    status: Optional[PaymentOrderStatus] = None,
    gateway_type: Optional[PaymentGatewayType] = None,
    purchase_type: Optional[PurchaseType] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    search: Optional[str] = None,
    user_id: Optional[int] = None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [_NOT_TEST]
    if user_id is not None:
        filters.append(PaymentOrder.user_id == user_id)
    if status is not None:
        filters.append(PaymentOrder.status == status)
    if gateway_type is not None:
        filters.append(PaymentOrder.gateway_type == gateway_type)
    if purchase_type is not None:
        filters.append(PaymentOrder.purchase_type == purchase_type)
    if created_from is not None:
        filters.append(PaymentOrder.created_at >= created_from)
    if created_to is not None:
        filters.append(PaymentOrder.created_at < created_to)
    if search:
        pattern = f"%{search}%"
        search_filters: list[ColumnElement[bool]] = [
            PaymentOrder.external_payment_id.ilike(pattern),
            PaymentOrder.customer_email.ilike(pattern),
            PaymentOrder.plan_snapshot["name"].astext.ilike(pattern),
        ]
        # id/user_id are Integer; a longer digit string would overflow asyncpg
        if search.isdigit() and int(search) <= INT32_MAX:
            search_filters += [
                PaymentOrder.id == int(search),
                PaymentOrder.user_id == int(search),
            ]
        filters.append(or_(*search_filters))
    return filters


class PaymentOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: PaymentOrder) -> PaymentOrderDto:
        return PaymentOrderDto(
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

    async def create(self, data: CreatePaymentOrderDto) -> PaymentOrderDto:
        row = PaymentOrder(
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

    async def get_by_id(self, order_id: int) -> PaymentOrderDto:
        row = await self.session.get(PaymentOrder, order_id)
        if row is None:
            raise NotFoundError(f"PaymentOrder '{order_id}' not found")
        return self._to_dto(row)

    async def get_by_idempotency_key(
        self, key: str, *, gateway_type: Optional[PaymentGatewayType] = None
    ) -> Optional[PaymentOrderDto]:
        filters = [PaymentOrder.idempotency_key == key]
        if gateway_type is not None:
            filters.append(PaymentOrder.gateway_type == gateway_type)
        row = await self.session.scalar(select(PaymentOrder).where(*filters))
        return self._to_dto(row) if row is not None else None

    async def get_by_external_payment_id(
        self, external_id: str, *, gateway_type: Optional[PaymentGatewayType] = None
    ) -> Optional[PaymentOrderDto]:
        # external_payment_id is unique per gateway, not globally -- two
        # providers can hand out the same id, so a caller that knows which
        # gateway it is asking about passes it.
        filters = [PaymentOrder.external_payment_id == external_id]
        if gateway_type is not None:
            filters.append(PaymentOrder.gateway_type == gateway_type)
        row = await self.session.scalar(select(PaymentOrder).where(*filters))
        return self._to_dto(row) if row is not None else None

    async def mark_status(
        self,
        order_id: int,
        status: PaymentOrderStatus,
        *,
        external_payment_id: Optional[str] = None,
    ) -> PaymentOrderDto:
        row = await self.session.get(PaymentOrder, order_id)
        if row is None:
            raise NotFoundError(f"PaymentOrder '{order_id}' not found")
        row.status = status
        if external_payment_id is not None:
            row.external_payment_id = external_payment_id
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def mark_status_if(
        self,
        order_id: int,
        status: PaymentOrderStatus,
        *,
        current: frozenset[PaymentOrderStatus],
    ) -> bool:
        # conditional in SQL so a status that landed meanwhile (e.g. PAID) wins
        result = await self.session.execute(
            update(PaymentOrder)
            .where(PaymentOrder.id == order_id, PaymentOrder.status.in_(current))
            .values(status=status, updated_at=NOW_FUNC)
        )
        return cast(CursorResult, result).rowcount > 0

    async def list_expired_pending(self, cutoff: datetime) -> list[PaymentOrderDto]:
        rows = (
            await self.session.scalars(
                select(PaymentOrder).where(
                    PaymentOrder.status == PaymentOrderStatus.PENDING,
                    PaymentOrder.expires_at <= cutoff,
                )
            )
        ).all()
        return [self._to_dto(row) for row in rows]

    async def cancel_expired_pending(self, cutoff: datetime) -> int:
        # A bulk Core update() bypasses the ORM's attribute-level onupdate
        # hook, so updated_at (shown in the admin router) has to be set
        # explicitly here -- it wouldn't otherwise bump on this path.
        result = await self.session.execute(
            update(PaymentOrder)
            .where(
                PaymentOrder.status == PaymentOrderStatus.PENDING,
                PaymentOrder.expires_at <= cutoff,
            )
            .values(status=PaymentOrderStatus.CANCELED, updated_at=NOW_FUNC)
        )
        return cast(CursorResult, result).rowcount

    async def list_paid_awaiting_reconciliation(
        self, cutoff: datetime, *, since: datetime
    ) -> list[PaymentOrderDto]:
        rows = (
            await self.session.scalars(
                select(PaymentOrder).where(
                    PaymentOrder.status == PaymentOrderStatus.PAID,
                    _NOT_TEST,
                    PaymentOrder.fulfilled_at.is_(None),
                    PaymentOrder.updated_at <= cutoff,
                    PaymentOrder.updated_at >= since,
                )
            )
        ).all()
        return [self._to_dto(row) for row in rows]

    async def mark_fulfilled(self, order_id: int) -> None:
        # updated_at is the paid-at timestamp every revenue query groups by --
        # pinned to itself, since Core update() still applies its onupdate.
        await self.session.execute(
            update(PaymentOrder)
            .where(PaymentOrder.id == order_id, PaymentOrder.fulfilled_at.is_(None))
            .values(fulfilled_at=NOW_FUNC, updated_at=PaymentOrder.updated_at)
        )

    async def list_paginated(
        self,
        *,
        status: Optional[PaymentOrderStatus] = None,
        gateway_type: Optional[PaymentGatewayType] = None,
        purchase_type: Optional[PurchaseType] = None,
        created_from: Optional[datetime] = None,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[PaymentOrderDto], int]:
        filters = _order_filters(
            status=status,
            gateway_type=gateway_type,
            purchase_type=purchase_type,
            created_from=created_from,
            search=search,
            user_id=user_id,
        )

        count_stmt = select(func.count()).select_from(PaymentOrder).where(*filters)
        total = await self.session.scalar(count_stmt)

        stmt = (
            select(PaymentOrder)
            .where(*filters)
            .order_by(PaymentOrder.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()
        return [self._to_dto(row) for row in rows], int(total or 0)

    async def summarize(
        self,
        *,
        status: Optional[PaymentOrderStatus] = None,
        gateway_type: Optional[PaymentGatewayType] = None,
        purchase_type: Optional[PurchaseType] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> list[tuple[PaymentOrderStatus, Currency, int, Decimal, Decimal]]:
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
                PaymentOrder.status,
                PaymentOrder.currency,
                func.count(),
                func.sum(PaymentOrder.final_price),
                func.sum(PaymentOrder.base_price),
            )
            .where(*filters)
            .group_by(PaymentOrder.status, PaymentOrder.currency)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return list(rows.all())

    async def list_gateway_types(self) -> list[PaymentGatewayType]:
        rows = await self.session.scalars(
            select(PaymentOrder.gateway_type)
            .where(_NOT_TEST)
            .distinct()
            .order_by(PaymentOrder.gateway_type)
        )
        return list(rows)

    async def sum_paid_final_price_by_user_ids(
        self, user_ids: list[int]
    ) -> dict[Currency, Decimal]:
        if not user_ids:
            return {}
        totals: dict[Currency, Decimal] = {}
        for start in range(0, len(user_ids), _MAX_IN_PARAMS):
            chunk = user_ids[start : start + _MAX_IN_PARAMS]
            stmt = (
                select(PaymentOrder.currency, func.sum(PaymentOrder.final_price))
                .where(
                    PaymentOrder.user_id.in_(chunk),
                    PaymentOrder.status == PaymentOrderStatus.PAID,
                    _NOT_TEST,
                )
                .group_by(PaymentOrder.currency)
            )
            rows = (await self.session.execute(stmt)).tuples()
            for currency, amount in rows.all():
                totals[currency] = totals.get(currency, Decimal(0)) + amount
        return totals

    async def sum_paid_promocode_discounts(self) -> tuple[int, dict[Currency, Decimal]]:
        # (paid orders, discount amount per currency)
        stmt = (
            select(
                PaymentOrder.currency,
                func.count(),
                func.sum(PaymentOrder.base_price - PaymentOrder.final_price),
            )
            .where(
                PaymentOrder.status == PaymentOrderStatus.PAID,
                PaymentOrder.discount_promocode_id.is_not(None),
                _NOT_TEST,
            )
            .group_by(PaymentOrder.currency)
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
        for start in range(0, len(user_ids), _MAX_IN_PARAMS):
            chunk = user_ids[start : start + _MAX_IN_PARAMS]
            stmt = select(PaymentOrder.user_id.distinct()).where(
                PaymentOrder.user_id.in_(chunk),
                PaymentOrder.status == PaymentOrderStatus.PAID,
                _NOT_TEST,
            )
            result = await self.session.execute(stmt)
            paid.update(result.scalars().all())
        return paid

    async def list_user_ids_with_multiple_paid_orders(self, user_ids: list[int]) -> set[int]:
        if not user_ids:
            return set()
        repeat_payers: set[int] = set()
        for start in range(0, len(user_ids), _MAX_IN_PARAMS):
            chunk = user_ids[start : start + _MAX_IN_PARAMS]
            stmt = (
                select(PaymentOrder.user_id)
                .where(
                    PaymentOrder.user_id.in_(chunk),
                    PaymentOrder.status == PaymentOrderStatus.PAID,
                    _NOT_TEST,
                )
                .group_by(PaymentOrder.user_id)
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
            func.date_trunc("month", func.timezone("UTC", PaymentOrder.updated_at))
        )
        pairs: list[tuple[int, date]] = []
        for start in range(0, len(user_ids), _MAX_IN_PARAMS):
            chunk = user_ids[start : start + _MAX_IN_PARAMS]
            stmt = (
                select(PaymentOrder.user_id, month_col)
                .where(
                    PaymentOrder.user_id.in_(chunk),
                    PaymentOrder.status == PaymentOrderStatus.PAID,
                    _NOT_TEST,
                    PaymentOrder.updated_at >= since,
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
            select(PaymentOrder.user_id, PaymentOrder.currency, func.sum(PaymentOrder.final_price))
            .where(PaymentOrder.status == PaymentOrderStatus.PAID, _NOT_TEST)
            .group_by(PaymentOrder.user_id, PaymentOrder.currency)
        )
        if user_ids is not None:
            stmt = stmt.where(PaymentOrder.user_id.in_(user_ids))
        if created_before is not None:
            stmt = stmt.where(PaymentOrder.created_at < created_before)
        rows = (await self.session.execute(stmt)).tuples()
        totals: dict[int, dict[Currency, Decimal]] = {}
        for user_id, currency, amount in rows.all():
            totals.setdefault(user_id, {})[currency] = amount
        return totals

    async def count_paid_since(self, since: datetime) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).where(
                    PaymentOrder.status == PaymentOrderStatus.PAID,
                    _NOT_TEST,
                    PaymentOrder.updated_at >= since,
                )
            )
            or 0
        )

    async def sum_paid_final_price_since(self, since: datetime) -> dict[Currency, Decimal]:
        stmt = (
            select(PaymentOrder.currency, func.sum(PaymentOrder.final_price))
            .where(
                PaymentOrder.status == PaymentOrderStatus.PAID,
                _NOT_TEST,
                PaymentOrder.updated_at >= since,
            )
            .group_by(PaymentOrder.currency)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return dict(rows.all())

    async def daily_paid_revenue_by_currency(
        self, since: datetime
    ) -> dict[date, dict[Currency, Decimal]]:
        day_col = func.date(func.timezone("UTC", PaymentOrder.updated_at))
        stmt = (
            select(day_col, PaymentOrder.currency, func.sum(PaymentOrder.final_price))
            .where(
                PaymentOrder.status == PaymentOrderStatus.PAID,
                _NOT_TEST,
                PaymentOrder.updated_at >= since,
            )
            .group_by(day_col, PaymentOrder.currency)
            .order_by(day_col)
        )
        rows = (await self.session.execute(stmt)).tuples()
        result: dict[date, dict[Currency, Decimal]] = {}
        for day, currency, amount in rows.all():
            result.setdefault(day, {})[currency] = amount
        return result

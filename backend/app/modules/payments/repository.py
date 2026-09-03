from datetime import datetime
from decimal import Decimal
from typing import Final, Optional, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.payment_order import PaymentOrder
from app.core.db.timestamp import NOW_FUNC
from app.core.enums import Currency, PaymentOrderStatus
from app.core.exceptions import NotFoundError
from app.modules.payments.dto import DEFAULT_PAGE_SIZE, CreatePaymentOrderDto, PaymentOrderDto
from app.modules.subscriptions import PlanSnapshot

# asyncpg caps a statement at 32,767 bind parameters; stay well under that so a
# large attributed-user list still fits after other predicates are added.
_MAX_IN_PARAMS: Final[int] = 20_000


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
            customer_email=row.customer_email,
            idempotency_key=row.idempotency_key,
            expires_at=row.expires_at,
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
            customer_email=data.customer_email,
            idempotency_key=data.idempotency_key,
            expires_at=data.expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return self._to_dto(row)

    async def get_by_id(self, order_id: int) -> PaymentOrderDto:
        row = await self.session.get(PaymentOrder, order_id)
        if row is None:
            raise NotFoundError(f"PaymentOrder '{order_id}' not found")
        return self._to_dto(row)

    async def get_by_idempotency_key(self, key: str) -> Optional[PaymentOrderDto]:
        row = await self.session.scalar(
            select(PaymentOrder).where(PaymentOrder.idempotency_key == key)
        )
        return self._to_dto(row) if row is not None else None

    async def get_by_external_payment_id(self, external_id: str) -> Optional[PaymentOrderDto]:
        row = await self.session.scalar(
            select(PaymentOrder).where(PaymentOrder.external_payment_id == external_id)
        )
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

    async def mark_expired_pending(self, cutoff: datetime) -> int:
        # A bulk Core update() bypasses the ORM's attribute-level onupdate
        # hook, so updated_at (shown in the admin router) has to be set
        # explicitly here -- it wouldn't otherwise bump on this path.
        result = await self.session.execute(
            update(PaymentOrder)
            .where(
                PaymentOrder.status == PaymentOrderStatus.PENDING,
                PaymentOrder.expires_at <= cutoff,
            )
            .values(status=PaymentOrderStatus.EXPIRED, updated_at=NOW_FUNC)
        )
        return cast(CursorResult, result).rowcount

    async def list_paid_awaiting_reconciliation(self, cutoff: datetime) -> list[PaymentOrderDto]:
        # unbounded scan of every PAID order ever marked before
        # `cutoff` -- fine at this project's current scale (no production
        # traffic yet). Add a lower bound on created_at (or an index-assisted
        # cursor) if this table grows large enough for the scan to matter.
        rows = (
            await self.session.scalars(
                select(PaymentOrder).where(
                    PaymentOrder.status == PaymentOrderStatus.PAID,
                    PaymentOrder.updated_at <= cutoff,
                )
            )
        ).all()
        return [self._to_dto(row) for row in rows]

    async def list_paginated(
        self,
        *,
        status: Optional[PaymentOrderStatus] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[PaymentOrderDto], int]:
        filters = [PaymentOrder.status == status] if status is not None else []

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
                )
                .group_by(PaymentOrder.currency)
            )
            rows = (await self.session.execute(stmt)).tuples()
            for currency, amount in rows.all():
                totals[currency] = totals.get(currency, Decimal(0)) + amount
        return totals

    async def list_user_ids_with_paid_order(self, user_ids: list[int]) -> set[int]:
        if not user_ids:
            return set()
        paid: set[int] = set()
        for start in range(0, len(user_ids), _MAX_IN_PARAMS):
            chunk = user_ids[start : start + _MAX_IN_PARAMS]
            stmt = select(PaymentOrder.user_id.distinct()).where(
                PaymentOrder.user_id.in_(chunk),
                PaymentOrder.status == PaymentOrderStatus.PAID,
            )
            result = await self.session.execute(stmt)
            paid.update(result.scalars().all())
        return paid

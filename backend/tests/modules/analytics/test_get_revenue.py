from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.transaction import Transaction
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Locale,
    PaymentGatewayType,
    PurchaseType,
    Role,
    TransactionStatus,
)
from app.core.exceptions import PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.analytics.dto import GetRevenueDto
from app.modules.analytics.usecases import GetRevenueUseCase
from app.modules.pricing.repository import PricingRepository
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.stats_repository import UserStatsRepository
from tests.fakes.analytics_cache import PassThroughAnalyticsCache
from tests.modules.analytics.test_get_analytics import _paid_order_dto

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _use_case(
    session: AsyncSession, pricing_repository: PricingRepository, uow: UnitOfWork
) -> GetRevenueUseCase:
    return GetRevenueUseCase(
        UserStatsRepository(session),
        TransactionStatsRepository(session),
        pricing_repository,
        uow,
        PassThroughAnalyticsCache(),
    )


def _midnight() -> datetime:
    return datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)


async def _seed(
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    *,
    user_id: int,
    plan_id: int,
    key: str,
    at: datetime,
    price: str,
    status: TransactionStatus,
    purchase_type: PurchaseType = PurchaseType.NEW,
    gateway: PaymentGatewayType = PaymentGatewayType.YOOKASSA,
    duration_days: int = 30,
) -> None:
    dto = replace(
        _paid_order_dto(
            user_id=user_id,
            plan_id=plan_id,
            idempotency_key=key,
            final_price=Decimal(price),
            duration_days=duration_days,
        ),
        purchase_type=purchase_type,
        gateway_type=gateway,
    )
    async with uow:
        order = await transaction_repository.create(dto)
    await transaction_repository.mark_status(order.id, status)
    await session.execute(
        update(Transaction).where(Transaction.id == order.id).values(created_at=at, updated_at=at)
    )


async def test_actor_without_revenue_view_is_denied(
    pricing_repository: PricingRepository, session: AsyncSession, uow: UnitOfWork
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})

    with pytest.raises(PermissionDeniedError):
        await _use_case(session, pricing_repository, uow)(actor, GetRevenueDto())


async def test_revenue_by_purchase_type_plan_and_gateway(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=850_001))
    start = _midnight() - timedelta(days=14)
    end = start + timedelta(days=14)

    async def seed(
        key: str, day: float, price: str, status: TransactionStatus, **kw: object
    ) -> None:
        await _seed(
            transaction_repository,
            session,
            uow,
            user_id=user.id,
            plan_id=plan_id,
            key=key,
            at=start + timedelta(days=day),
            price=price,
            status=status,
            **kw,  # type: ignore[arg-type]
        )

    paid = TransactionStatus.PAID
    await seed("r-new", 1.5, "500", paid)
    await seed("r-renew", 9.5, "300", paid, purchase_type=PurchaseType.RENEW, duration_days=90)
    await seed("r-change", 10.5, "200", paid, purchase_type=PurchaseType.CHANGE)
    await seed(
        "r-refund", 3.5, "150", TransactionStatus.REFUNDED, gateway=PaymentGatewayType.CRYPTOMUS
    )
    await seed("r-fail", 2.5, "100", TransactionStatus.FAILED, gateway=PaymentGatewayType.CRYPTOMUS)
    await seed("r-prev", -3.5, "400", paid)

    revenue = await _use_case(session, pricing_repository, uow)(
        OWNER,
        GetRevenueDto(period_from=start, period_to=end - timedelta(days=1), granularity="week"),
    )

    assert revenue.totals.revenue == Decimal("1000")
    assert revenue.totals.payments == 3
    assert revenue.totals.median_check == Decimal("300")
    assert revenue.totals.refunds == 1 and revenue.totals.refunded == Decimal("150")
    assert revenue.totals.previous_revenue == Decimal("400")
    assert [b.new for b in revenue.series] == [Decimal("500"), Decimal(0)]
    assert revenue.series[1].renew == Decimal("300") and revenue.series[1].change == Decimal("200")
    assert sum(b.previous_total for b in revenue.series) == Decimal("400")
    assert revenue.by_duration[0].key == "30"
    by_gateway = {g.gateway_type: (g.paid, g.failed, g.refunded) for g in revenue.gateways}
    assert by_gateway[PaymentGatewayType.CRYPTOMUS] == (0, 1, 1)
    assert by_gateway[PaymentGatewayType.YOOKASSA][0] == 3
    assert sum(g.paid for g in revenue.gateways) == revenue.totals.payments


async def test_revenue_on_an_empty_period_is_zero(
    pricing_repository: PricingRepository, session: AsyncSession, uow: UnitOfWork
) -> None:
    start = _midnight() - timedelta(days=6)
    revenue = await _use_case(session, pricing_repository, uow)(
        OWNER, GetRevenueDto(period_from=start, period_to=start + timedelta(days=6))
    )

    assert len(revenue.series) == (revenue.period.end - revenue.period.start).days
    assert all(
        b.new == b.renew == b.change == b.previous_total == Decimal(0) for b in revenue.series
    )
    assert revenue.totals.revenue == Decimal(0) and revenue.totals.avg_check == Decimal(0)
    assert revenue.by_plan == [] and revenue.gateways == []

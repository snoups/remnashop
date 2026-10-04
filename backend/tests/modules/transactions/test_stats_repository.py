from datetime import timedelta
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.transaction import Transaction
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseType,
    TransactionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot


def _order(user_id: int, plan_id: int, key: str) -> CreateTransactionDto:
    return CreateTransactionDto(
        user_id=user_id,
        plan_id=plan_id,
        plan_snapshot=make_plan_snapshot(plan_id=plan_id),
        duration_days=30,
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        target_subscription_id=None,
        gateway_type=PaymentGatewayType.YOOKASSA,
        base_price=Decimal("500"),
        discount_percent=0,
        discount_source=DiscountSource.NONE,
        final_price=Decimal("500"),
        customer_email=None,
        idempotency_key=key,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


async def test_list_paid_returns_only_paid_non_test_rows_in_range(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=861_001))
    async with uow:
        paid = await transaction_repository.create(_order(user.id, plan_id, "stats-1"))
        await transaction_repository.create(_order(user.id, plan_id, "stats-2"))
        old = await transaction_repository.create(_order(user.id, plan_id, "stats-3"))
    for order in (paid, old):
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction)
        .where(Transaction.id == old.id)
        .values(updated_at=datetime_now() - timedelta(days=40))
    )
    repo = TransactionStatsRepository(session)

    rows = await repo.list_paid(
        datetime_now() - timedelta(days=30), datetime_now() + timedelta(seconds=1)
    )

    assert [row.user_id for row in rows] == [user.id]
    assert rows[0].plan_name == "Basic"
    assert len(await repo.list_paid(None, datetime_now() + timedelta(seconds=1))) == 2
    attempts = await repo.list_attempts(
        datetime_now() - timedelta(days=1), datetime_now() + timedelta(seconds=1)
    )
    assert sorted(a.status for a in attempts) == sorted(
        [TransactionStatus.PAID, TransactionStatus.PENDING, TransactionStatus.PAID]
    )


async def test_list_recent_paid_returns_newest_first(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=861_002))
    async with uow:
        orders = [
            await transaction_repository.create(_order(user.id, plan_id, f"recent-{i}"))
            for i in range(4)
        ]
    for order in orders[:3]:
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
    for order, hours in zip(orders[:3], (3, 2, 1)):
        await session.execute(
            update(Transaction)
            .where(Transaction.id == order.id)
            .values(updated_at=datetime_now() + timedelta(days=1, hours=-hours))
        )

    rows = await TransactionStatsRepository(session).list_recent_paid(2)

    assert [row.paid_at for row in rows] == sorted((row.paid_at for row in rows), reverse=True)
    assert len(rows) == 2
    assert rows[0].paid_at > datetime_now() + timedelta(hours=22)
    assert rows[1].paid_at > datetime_now() + timedelta(hours=21)
    assert rows[0].paid_at > rows[1].paid_at


async def test_count_failed_by_gateway_and_stale_pending(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=861_003))
    now = datetime_now()
    async with uow:
        failed = await transaction_repository.create(_order(user.id, plan_id, "cnt-1"))
        old_failed = await transaction_repository.create(_order(user.id, plan_id, "cnt-2"))
        stale = await transaction_repository.create(_order(user.id, plan_id, "cnt-3"))
        await transaction_repository.create(_order(user.id, plan_id, "cnt-4"))
    for order in (failed, old_failed):
        await transaction_repository.mark_status(order.id, TransactionStatus.FAILED)
    await session.execute(
        update(Transaction)
        .where(Transaction.id == old_failed.id)
        .values(updated_at=now - timedelta(hours=3))
    )
    await session.execute(
        update(Transaction)
        .where(Transaction.id == stale.id)
        .values(created_at=now - timedelta(hours=1))
    )
    repo = TransactionStatsRepository(session)

    failed_by_gateway = await repo.count_failed_by_gateway(now - timedelta(hours=1))
    stale_count = await repo.count_stale_pending(now - timedelta(minutes=30), now)

    assert failed_by_gateway[PaymentGatewayType.YOOKASSA] == 1
    assert stale_count == 1

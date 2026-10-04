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

import random
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
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
from app.modules.analytics.coverage import is_covered, paid_coverage
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
        anchor_base_price=Decimal("500"),
        anchor_final_price=Decimal("500"),
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
        paid = await transaction_repository.create(
            replace(
                _order(user.id, plan_id, "stats-1"),
                anchor_base_price=Decimal("7"),
                anchor_final_price=Decimal("6"),
            )
        )
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
    assert (rows[0].anchor_base_price, rows[0].anchor_final_price) == (Decimal("7"), Decimal("6"))
    assert rows[0].plan_discount_percent == 0
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


async def _paid_history(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
    seed: int,
) -> dict[int, list[tuple[datetime, int]]]:
    rng = random.Random(seed)
    base = datetime_now() - timedelta(days=400)
    history: dict[int, list[tuple[datetime, int]]] = {}
    for u in range(6):
        user = await user_repository.create(
            CreateUserDto(name="cov", telegram_id=862_000 + seed * 10 + u)
        )
        payments: list[tuple[datetime, int]] = []
        for n in range(rng.randint(1, 6)):
            paid_at = base + timedelta(days=rng.randint(0, 380), hours=rng.randint(0, 23))
            days = rng.choice((7, 30, 30, 90, 365))
            async with uow:
                order = await transaction_repository.create(
                    _order(user.id, plan_id, f"cov-{seed}-{u}-{n}")
                )
            await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
            await session.execute(
                update(Transaction)
                .where(Transaction.id == order.id)
                .values(updated_at=paid_at, duration_days=days)
            )
            payments.append((paid_at, days))
        history[user.id] = payments
    return history


@pytest.mark.parametrize("seed", [1, 2, 3])
async def test_sql_coverage_matches_the_python_reference(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
    seed: int,
) -> None:
    history = await _paid_history(
        user_repository, transaction_repository, session, uow, plan_id, seed
    )
    stats = TransactionStatsRepository(session)
    now = datetime_now()
    coverage = {user_id: paid_coverage(p) for user_id, p in history.items()}
    ours = set(history)
    points_at = [now + timedelta(days=offset) for offset in range(-400, 400, 13)]
    covered = await stats.users_covered_at(points_at, now)
    for point in points_at:
        expected = {u for u, segments in coverage.items() if is_covered(segments, point)}
        assert covered[point] & ours == expected, point

    rng = random.Random(seed)
    points = {u: now - timedelta(days=rng.randint(0, 400)) for u in history}
    expected_points = {u for u, at in points.items() if is_covered(coverage[u], at)}
    assert await stats.users_covered_at_their_points(points, now) == expected_points

    payers, days = await stats.total_covered_days(now)
    assert payers >= len(history)


async def test_total_covered_days_matches_the_python_reference(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    stats = TransactionStatsRepository(session)
    now = datetime_now()
    before_payers, before_days = await stats.total_covered_days(now)
    history = await _paid_history(
        user_repository, transaction_repository, session, uow, plan_id, seed=7
    )
    expected = sum(
        max((min(end, now) - start).total_seconds(), 0.0) / 86400
        for payments in history.values()
        for start, end in paid_coverage(payments)
    )
    payers, days = await stats.total_covered_days(now)
    assert payers - before_payers == len(history)
    assert days - before_days == pytest.approx(expected, abs=1e-3)

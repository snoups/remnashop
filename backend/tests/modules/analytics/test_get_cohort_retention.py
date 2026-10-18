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
    Locale,
    PaymentGatewayType,
    PurchaseType,
    Role,
    TransactionStatus,
)
from app.core.exceptions import PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.analytics.usecases import GetCohortRetentionUseCase
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.analytics_cache import PassThroughAnalyticsCache
from tests.modules.subscriptions.factories import make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _paid_order_dto(
    *, user_id: int, plan_id: int, idempotency_key: str, duration_days: int = 30
) -> CreateTransactionDto:
    return CreateTransactionDto(
        user_id=user_id,
        plan_id=plan_id,
        plan_snapshot=make_plan_snapshot(plan_id=plan_id),
        duration_days=duration_days,
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
        idempotency_key=idempotency_key,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


async def test_actor_without_analytics_view_is_denied(
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})
    use_case = GetCohortRetentionUseCase(transaction_repository, uow, PassThroughAnalyticsCache())

    with pytest.raises(PermissionDeniedError):
        await use_case(actor)


async def test_cohort_counts_paid_coverage_per_month(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    month = datetime_now().replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    for _ in range(4):
        month = (month - timedelta(days=1)).replace(day=1)
    cohort_day = month.replace(day=2)
    later_month = month
    for _ in range(3):
        later_month = (later_month + timedelta(days=32)).replace(day=1)
    later_day = later_month.replace(day=2)

    async def pay(
        telegram_id: int,
        payments: list[tuple[datetime, int]],
        status: TransactionStatus = TransactionStatus.PAID,
    ) -> None:
        user = await user_repository.create(CreateUserDto(name="U", telegram_id=telegram_id))
        for n, (paid_at, days) in enumerate(payments):
            async with uow:
                order = await transaction_repository.create(
                    _paid_order_dto(
                        user_id=user.id,
                        plan_id=plan_id,
                        idempotency_key=f"cohort-{telegram_id}-{n}",
                        duration_days=days,
                    )
                )
            await transaction_repository.mark_status(order.id, status)
            await session.execute(
                update(Transaction).where(Transaction.id == order.id).values(updated_at=paid_at)
            )

    await pay(829_101, [(cohort_day, 20), (later_day, 20)])  # gap in M1-M2
    await pay(829_102, [(cohort_day, 20), (cohort_day + timedelta(days=10), 30)])  # early renewal
    await pay(829_103, [(cohort_day, 20)], status=TransactionStatus.REFUNDED)

    result = await GetCohortRetentionUseCase(
        transaction_repository, uow, PassThroughAnalyticsCache()
    )(OWNER)

    row = next(r for r in result.cohorts if r.cohort == cohort_day.strftime("%Y-%m"))
    assert row.cohort_size == 2
    assert row.retention_by_month == pytest.approx([1.0, 0.5, 0.0, 0.5, 0.0])


async def test_cohort_since_is_timezone_aware(
    transaction_repository: TransactionRepository, uow: UnitOfWork
) -> None:
    captured: dict[str, datetime] = {}
    original = transaction_repository.first_paid_at_since

    async def _spy(since: datetime) -> dict[int, datetime]:
        captured["since"] = since
        return await original(since)

    transaction_repository.first_paid_at_since = _spy  # type: ignore[method-assign]
    await GetCohortRetentionUseCase(transaction_repository, uow, PassThroughAnalyticsCache())(OWNER)

    assert captured["since"].tzinfo is not None


@pytest.mark.parametrize(("renewed", "expected_m1"), [(False, 0.0), (True, 1.0)])
async def test_cohort_month_is_measured_at_the_payment_anniversary(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
    renewed: bool,
    expected_m1: float,
) -> None:
    month = datetime_now().replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    for _ in range(2):
        month = (month - timedelta(days=1)).replace(day=1)
    first_paid_at = month.replace(day=15)
    # 28 days ends before the next month's 15th even after a February
    payments = [(first_paid_at, 28)]
    if renewed:
        payments.append((first_paid_at + timedelta(days=25), 28))

    user = await user_repository.create(CreateUserDto(name="U", telegram_id=829_201))
    for n, (paid_at, days) in enumerate(payments):
        async with uow:
            order = await transaction_repository.create(
                _paid_order_dto(
                    user_id=user.id,
                    plan_id=plan_id,
                    idempotency_key=f"anniversary-{n}",
                    duration_days=days,
                )
            )
        await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
        await session.execute(
            update(Transaction).where(Transaction.id == order.id).values(updated_at=paid_at)
        )

    result = await GetCohortRetentionUseCase(
        transaction_repository, uow, PassThroughAnalyticsCache()
    )(OWNER)

    row = next(r for r in result.cohorts if r.cohort == first_paid_at.strftime("%Y-%m"))
    assert row.cohort_size == 1
    assert row.retention_by_month[1] == expected_m1

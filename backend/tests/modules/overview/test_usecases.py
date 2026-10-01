import os
import time
from datetime import timedelta
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.transaction import Transaction
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    Locale,
    PaymentGatewayType,
    PurchaseType,
    Role,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.runtime_heartbeat import publish_runtime_heartbeat
from app.core.utils.time import datetime_now
from app.modules.overview.dto import GetOverviewDto
from app.modules.overview.usecases import GetOverviewUseCase
from app.modules.pricing.repository import PricingRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import create_subscription, make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _paid_order_dto(*, user_id: int, plan_id: int, idempotency_key: str) -> CreateTransactionDto:
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
        idempotency_key=idempotency_key,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


async def test_owner_sees_all_sections_with_correct_counts(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    payer = await user_repository.create(CreateUserDto(name="Payer", telegram_id=830_001))
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=830_002,
        remnawave_user_id=830_002,
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime_now() + timedelta(days=3),
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=830_003,
        remnawave_user_id=830_003,
        status=SubscriptionStatus.LIMITED,
        expire_at=datetime_now() + timedelta(days=30),
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=830_004,
        remnawave_user_id=830_004,
        status=SubscriptionStatus.EXPIRED,
        expire_at=datetime_now() - timedelta(days=1),
    )
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="overview-owner-1")
        )
    await transaction_repository.mark_status(order.id, TransactionStatus.PAID)

    use_case = GetOverviewUseCase(
        user_repository,
        subscription_repository,
        transaction_repository,
        pricing_repository,
        redis,
        uow,
    )
    overview = await use_case(OWNER, GetOverviewDto(days=7))

    assert overview.users is not None
    assert overview.users.total >= 1
    assert overview.subscriptions is not None
    assert overview.subscriptions.active == 1
    assert overview.subscriptions.limited == 1
    assert overview.subscriptions.expired == 1
    assert overview.subscriptions.total == 3
    assert overview.subscriptions.expiring_soon == 1
    assert overview.transactions is not None
    assert overview.transactions.paid_orders_count >= 1
    assert overview.transactions.revenue_by_currency.get(Currency.RUB, Decimal(0)) >= Decimal("500")
    assert overview.online.current == 0
    assert overview.online.daily_peak == []


async def test_actor_missing_transactions_view_gets_transactions_none_but_keeps_other_sections(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    uow: UnitOfWork,
) -> None:
    actor = OWNER.model_copy(update={"permission_revokes": ["TRANSACTIONS_VIEW"]})

    use_case = GetOverviewUseCase(
        user_repository,
        subscription_repository,
        transaction_repository,
        pricing_repository,
        redis,
        uow,
    )
    overview = await use_case(actor, GetOverviewDto(days=7))

    assert overview.transactions is None
    assert overview.users is not None
    assert overview.subscriptions is not None


async def test_days_window_excludes_orders_paid_before_the_cutoff(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    payer = await user_repository.create(CreateUserDto(name="OldPayer", telegram_id=830_101))
    async with uow:
        old_order = await transaction_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="overview-old-1")
        )
    await transaction_repository.mark_status(old_order.id, TransactionStatus.PAID)
    # updated_at is a server default -- backdate this order outside the
    # usecase's own `days=7` window (same idiom as the Task 1/3 cutoff
    # tests) so this genuinely proves exclusion, not just inclusion.
    await session.execute(
        update(Transaction)
        .where(Transaction.id == old_order.id)
        .values(updated_at=datetime_now() - timedelta(days=10))
    )

    use_case = GetOverviewUseCase(
        user_repository,
        subscription_repository,
        transaction_repository,
        pricing_repository,
        redis,
        uow,
    )
    overview = await use_case(OWNER, GetOverviewDto(days=7))

    assert overview.transactions is not None
    assert overview.transactions.paid_orders_count == 0
    assert overview.transactions.revenue_by_currency == {}


async def test_since_is_calendar_aligned_not_a_rolling_cutoff(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    payer = await user_repository.create(CreateUserDto(name="TodayPayer", telegram_id=830_201))
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="overview-today-1")
        )
    await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
    # Backdate to 30 minutes into today (not yesterday) -- a rolling
    # `now - 1 day` cutoff would still include this, so this alone doesn't
    # distinguish the two window semantics. What does: with days=1, a
    # calendar-aligned `since` is midnight today, so an order backdated to
    # yesterday just before midnight must be excluded, while one backdated
    # to just after midnight today must be included.
    today_start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)
    await session.execute(
        update(Transaction)
        .where(Transaction.id == order.id)
        .values(updated_at=today_start + timedelta(minutes=30))
    )
    payer2 = await user_repository.create(CreateUserDto(name="YesterdayPayer", telegram_id=830_202))
    async with uow:
        old_order = await transaction_repository.create(
            _paid_order_dto(
                user_id=payer2.id, plan_id=plan_id, idempotency_key="overview-yesterday-1"
            )
        )
    await transaction_repository.mark_status(old_order.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction)
        .where(Transaction.id == old_order.id)
        .values(updated_at=today_start - timedelta(minutes=30))
    )

    use_case = GetOverviewUseCase(
        user_repository,
        subscription_repository,
        transaction_repository,
        pricing_repository,
        redis,
        uow,
    )
    overview = await use_case(OWNER, GetOverviewDto(days=1))

    assert overview.transactions is not None
    assert overview.transactions.paid_orders_count == 1


async def test_all_time_period_starts_at_first_registration_and_buckets_by_month(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    oldest = await user_repository.create(CreateUserDto(name="Oldest", telegram_id=830_301))
    await session.execute(
        update(User)
        .where(User.id == oldest.id)
        .values(created_at=datetime_now() - timedelta(days=200))
    )

    use_case = GetOverviewUseCase(
        user_repository,
        subscription_repository,
        transaction_repository,
        pricing_repository,
        redis,
        uow,
    )
    overview = await use_case(OWNER, GetOverviewDto(days=0))

    assert overview.granularity == "month"
    assert overview.users is not None
    month_starts = [entry.day for entry in overview.users.daily_registrations]
    assert all(m.day == 1 for m in month_starts)
    assert (datetime_now().date() - month_starts[0]).days >= 199
    # dense: every bucket is the first of the month after the previous one
    for earlier, later in zip(month_starts, month_starts[1:]):
        assert later == (earlier.replace(day=28) + timedelta(days=4)).replace(day=1)
    assert sum(entry.count for entry in overview.users.daily_registrations) >= 1


async def test_runtime_lists_only_processes_with_a_live_heartbeat(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    uow: UnitOfWork,
) -> None:
    keys = (
        "remnashop:runtime:heartbeat:api",
        "remnashop:runtime:heartbeat:telegram",
        "remnashop:runtime:heartbeat:worker",
    )
    await redis.delete(*keys)
    started_at = time.time() - 300
    await publish_runtime_heartbeat(
        redis,
        "api",
        pid=999,
        started_at=started_at,
        event_loop_delay_ms=1.5,
        event_loop_p99_ms=6.25,
    )

    use_case = GetOverviewUseCase(
        user_repository,
        subscription_repository,
        transaction_repository,
        pricing_repository,
        redis,
        uow,
    )
    overview = await use_case(OWNER, GetOverviewDto(days=7))

    assert len(overview.runtime) == 1
    process = overview.runtime[0]
    assert process.process == "api"
    assert process.pid == 999
    assert process.uptime_seconds >= 300
    assert process.rss_bytes > 0
    assert process.event_loop_delay_ms == 1.5
    assert process.event_loop_p99_ms == 6.25

    await redis.delete(*keys)


async def test_overview_includes_host_memory_when_available(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    uow: UnitOfWork,
) -> None:
    use_case = GetOverviewUseCase(
        user_repository,
        subscription_repository,
        transaction_repository,
        pricing_repository,
        redis,
        uow,
    )
    overview = await use_case(OWNER, GetOverviewDto(days=7))

    if overview.host_memory is not None:
        assert overview.host_memory.total_bytes > 0
        assert 0 <= overview.host_memory.used_bytes <= overview.host_memory.total_bytes
    else:
        assert not os.path.exists("/proc/meminfo")

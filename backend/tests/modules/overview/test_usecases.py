import os
import time
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
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
    PurchaseChannel,
    PurchaseType,
    Role,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.exceptions import PermissionDeniedError
from app.core.runtime_heartbeat import publish_runtime_heartbeat
from app.core.utils.time import datetime_now
from app.modules.overview.dto import GetOverviewChartDto
from app.modules.overview.usecases import (
    GetOnlineChartUseCase,
    GetOverviewUseCase,
    GetRevenueChartUseCase,
)
from app.modules.pricing.repository import PricingRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.stats_repository import UserStatsRepository
from tests.modules.subscriptions.factories import create_subscription, make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _paid_order_dto(*, user_id: int, plan_id: int, idempotency_key: str) -> CreateTransactionDto:
    return CreateTransactionDto(
        channel=PurchaseChannel.CABINET,
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
    subscription_stats_repository: SubscriptionStatsRepository,
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
        UserStatsRepository(user_repository.session),
        subscription_stats_repository,
        TransactionStatsRepository(user_repository.session),
        user_repository,
        pricing_repository,
        redis,
        uow,
    )
    overview = await use_case(OWNER)
    revenue = await GetRevenueChartUseCase(
        UserStatsRepository(user_repository.session),
        transaction_repository,
        pricing_repository,
        uow,
    )(OWNER, GetOverviewChartDto(days=7))
    online = await GetOnlineChartUseCase(UserStatsRepository(user_repository.session), redis, uow)(
        OWNER, GetOverviewChartDto(days=7)
    )

    assert overview.users is not None
    assert overview.users.total >= 1
    assert overview.subscriptions is not None
    assert overview.subscriptions.active == 1
    assert overview.subscriptions.limited == 1
    assert overview.subscriptions.expired == 1
    assert overview.subscriptions.total == 3
    assert overview.subscriptions.expiring_soon == 1
    assert overview.subscriptions.disabled == 0
    assert revenue.paid_orders_count >= 1
    assert revenue.revenue_by_currency.get(Currency.RUB, Decimal(0)) >= Decimal("500")
    assert online.current == 0
    assert online.daily_peak == []


async def test_actor_missing_transactions_view_is_denied_the_revenue_chart(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    uow: UnitOfWork,
    subscription_stats_repository: SubscriptionStatsRepository,
) -> None:
    actor = OWNER.model_copy(update={"permission_revokes": ["TRANSACTIONS_VIEW"]})

    use_case = GetRevenueChartUseCase(
        UserStatsRepository(user_repository.session),
        transaction_repository,
        pricing_repository,
        uow,
    )
    with pytest.raises(PermissionDeniedError):
        await use_case(actor, GetOverviewChartDto(days=7))


async def test_days_window_excludes_orders_paid_before_the_cutoff(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
    subscription_stats_repository: SubscriptionStatsRepository,
) -> None:
    payer = await user_repository.create(CreateUserDto(name="OldPayer", telegram_id=830_101))
    async with uow:
        old_order = await transaction_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="overview-old-1")
        )
    await transaction_repository.mark_status(old_order.id, TransactionStatus.PAID)
    # updated_at is a server default, so the order is backdated past the
    # usecase's `days=7` window by hand
    await session.execute(
        update(Transaction)
        .where(Transaction.id == old_order.id)
        .values(updated_at=datetime_now() - timedelta(days=10))
    )

    use_case = GetRevenueChartUseCase(
        UserStatsRepository(user_repository.session),
        transaction_repository,
        pricing_repository,
        uow,
    )
    revenue = await use_case(OWNER, GetOverviewChartDto(days=7))

    assert revenue.paid_orders_count == 0
    assert revenue.revenue_by_currency == {}


async def test_since_is_calendar_aligned_not_a_rolling_cutoff(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
    subscription_stats_repository: SubscriptionStatsRepository,
) -> None:
    payer = await user_repository.create(CreateUserDto(name="TodayPayer", telegram_id=830_201))
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="overview-today-1")
        )
    await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
    # With days=1 a calendar-aligned `since` is today's midnight: an order just
    # before it is out, one 30 minutes after is in. A rolling `now - 1 day`
    # cutoff would include both.
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

    use_case = GetRevenueChartUseCase(
        UserStatsRepository(user_repository.session),
        transaction_repository,
        pricing_repository,
        uow,
    )
    revenue = await use_case(OWNER, GetOverviewChartDto(days=1))

    assert revenue.paid_orders_count == 1


async def test_all_time_period_starts_at_first_registration_and_buckets_by_month(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    session: AsyncSession,
    uow: UnitOfWork,
    subscription_stats_repository: SubscriptionStatsRepository,
) -> None:
    oldest = await user_repository.create(CreateUserDto(name="Oldest", telegram_id=830_301))
    await session.execute(
        update(User)
        .where(User.id == oldest.id)
        .values(created_at=datetime_now() - timedelta(days=200))
    )

    use_case = GetRevenueChartUseCase(
        UserStatsRepository(user_repository.session),
        transaction_repository,
        pricing_repository,
        uow,
    )
    chart = await use_case(OWNER, GetOverviewChartDto(days=0))

    assert chart.granularity == "month"
    month_starts = [entry.day for entry in chart.daily]
    assert all(m.day == 1 for m in month_starts)
    assert (datetime_now().date() - month_starts[0]).days >= 199
    # dense: every bucket is the first of the month after the previous one
    for earlier, later in zip(month_starts, month_starts[1:]):
        assert later == (earlier.replace(day=28) + timedelta(days=4)).replace(day=1)


async def test_runtime_lists_only_processes_with_a_live_heartbeat(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    uow: UnitOfWork,
    subscription_stats_repository: SubscriptionStatsRepository,
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
        UserStatsRepository(user_repository.session),
        subscription_stats_repository,
        TransactionStatsRepository(user_repository.session),
        user_repository,
        pricing_repository,
        redis,
        uow,
    )
    overview = await use_case(OWNER)

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
    subscription_stats_repository: SubscriptionStatsRepository,
) -> None:
    use_case = GetOverviewUseCase(
        UserStatsRepository(user_repository.session),
        subscription_stats_repository,
        TransactionStatsRepository(user_repository.session),
        user_repository,
        pricing_repository,
        redis,
        uow,
    )
    overview = await use_case(OWNER)

    if overview.host_memory is not None:
        assert overview.host_memory.total_bytes > 0
        assert 0 <= overview.host_memory.used_bytes <= overview.host_memory.total_bytes
    else:
        assert not os.path.exists("/proc/meminfo")

    if overview.host is not None:
        assert overview.host.cpu_count >= 1
        assert overview.host.disk_total_bytes is not None
        assert overview.host.disk_total_bytes > 0


def _overview_use_case(
    user_repository: UserRepository,
    subscription_stats_repository: SubscriptionStatsRepository,
    pricing_repository: PricingRepository,
    redis: Redis,
    uow: UnitOfWork,
) -> GetOverviewUseCase:
    return GetOverviewUseCase(
        UserStatsRepository(user_repository.session),
        subscription_stats_repository,
        TransactionStatsRepository(user_repository.session),
        user_repository,
        pricing_repository,
        redis,
        uow,
    )


async def _seed_paid(
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    *,
    user_id: int,
    plan_id: int,
    key: str,
    amount: str,
    at: datetime,
) -> int:
    dto = _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key=key)
    dto = replace(
        dto,
        final_price=Decimal(amount),
        base_price=Decimal(amount),
        anchor_final_price=Decimal(amount),
        anchor_base_price=Decimal(amount),
    )
    async with uow:
        order = await transaction_repository.create(dto)
    await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction).where(Transaction.id == order.id).values(updated_at=at)
    )
    return order.id


def _now_and_midnight() -> tuple[datetime, datetime]:
    now = datetime_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now - today_start < timedelta(minutes=2):
        pytest.skip("too close to midnight to place today's rows")
    return now, today_start


async def _clear_window(session: AsyncSession, today_start: datetime, *, keep: list[int]) -> None:
    # foreign paid rows in the shared DB would skew the sums
    await session.execute(
        update(Transaction)
        .where(
            Transaction.updated_at >= today_start - timedelta(days=1),
            Transaction.id.not_in(keep),
        )
        .values(updated_at=datetime_now() - timedelta(days=3))
    )


async def test_revenue_today_compares_with_yesterday_same_time(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    subscription_stats_repository: SubscriptionStatsRepository,
    redis: Redis,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    payer = await user_repository.create(
        CreateUserDto(name="Rev Payer", telegram_id=830_201, username="revpayer")
    )
    now, today_start = _now_and_midnight()
    seeded = []
    for key, amount, at in (
        ("rev-today", "500", today_start + timedelta(minutes=1)),
        ("rev-yday-in", "400", today_start - timedelta(days=1, minutes=-1)),
        ("rev-yday-out", "900", now - timedelta(days=1) + timedelta(minutes=1)),
    ):
        seeded.append(
            await _seed_paid(
                transaction_repository,
                session,
                uow,
                user_id=payer.id,
                plan_id=plan_id,
                key=key,
                amount=amount,
                at=at,
            )
        )
    await _clear_window(session, today_start, keep=seeded)

    overview = await _overview_use_case(
        user_repository, subscription_stats_repository, pricing_repository, redis, uow
    )(OWNER)

    assert overview.revenue_today is not None
    assert overview.revenue_today.today == Decimal("500")
    assert overview.revenue_today.yesterday_same_time == Decimal("400")
    assert overview.revenue_today.change == pytest.approx(0.25)
    assert overview.recent_payments is not None
    newest = overview.recent_payments[0]
    assert newest.amount == Decimal("500")
    assert newest.name == "Rev Payer"
    assert newest.username == "revpayer"
    assert newest.currency == Currency.RUB


async def test_revenue_sections_hidden_without_transactions_view(
    user_repository: UserRepository,
    pricing_repository: PricingRepository,
    subscription_stats_repository: SubscriptionStatsRepository,
    redis: Redis,
    uow: UnitOfWork,
) -> None:
    actor = OWNER.model_copy(update={"permission_revokes": ["TRANSACTIONS_VIEW"]})

    overview = await _overview_use_case(
        user_repository, subscription_stats_repository, pricing_repository, redis, uow
    )(actor)

    assert overview.revenue_today is None
    assert overview.recent_payments is None


async def test_change_is_none_when_yesterday_had_no_revenue(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    subscription_stats_repository: SubscriptionStatsRepository,
    redis: Redis,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    payer = await user_repository.create(CreateUserDto(name="Solo", telegram_id=830_202))
    _, today_start = _now_and_midnight()
    seeded_id = await _seed_paid(
        transaction_repository,
        session,
        uow,
        user_id=payer.id,
        plan_id=plan_id,
        key="rev-solo",
        amount="500",
        at=today_start + timedelta(minutes=1),
    )
    await _clear_window(session, today_start, keep=[seeded_id])

    overview = await _overview_use_case(
        user_repository, subscription_stats_repository, pricing_repository, redis, uow
    )(OWNER)

    assert overview.revenue_today is not None
    assert overview.revenue_today.yesterday_same_time == Decimal("0")
    assert overview.revenue_today.change is None


async def test_subscriptions_split_paid_active_and_trials(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    pricing_repository: PricingRepository,
    subscription_stats_repository: SubscriptionStatsRepository,
    redis: Redis,
    uow: UnitOfWork,
) -> None:
    before = await subscription_stats_repository.count_paying(status=SubscriptionStatus.ACTIVE)
    trials_before = await subscription_stats_repository.count_active_trials()
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=830_203,
        remnawave_user_id=830_203,
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=830_204,
        remnawave_user_id=830_204,
        is_trial=True,
    )

    overview = await _overview_use_case(
        user_repository, subscription_stats_repository, pricing_repository, redis, uow
    )(OWNER)

    assert overview.subscriptions is not None
    assert overview.subscriptions.paid_active == before + 1
    assert overview.subscriptions.trials == trials_before + 1

from datetime import timedelta
from decimal import Decimal

import pytest
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
from app.core.exceptions import PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.analytics.dto import AnalyticsPeriodQueryDto
from app.modules.analytics.usecases import GetAnalyticsUseCase
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


def _paid_order_dto(
    *,
    user_id: int,
    plan_id: int,
    idempotency_key: str,
    final_price: Decimal = Decimal("500"),
    duration_days: int = 30,
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
        base_price=final_price,
        discount_percent=0,
        discount_source=DiscountSource.NONE,
        final_price=final_price,
        anchor_base_price=final_price,
        anchor_final_price=final_price,
        customer_email=None,
        idempotency_key=idempotency_key,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


def _use_case(
    session: AsyncSession, pricing_repository: PricingRepository, uow: UnitOfWork
) -> GetAnalyticsUseCase:
    return GetAnalyticsUseCase(
        UserStatsRepository(session),
        SubscriptionStatsRepository(session),
        TransactionStatsRepository(session),
        pricing_repository,
        uow,
    )


def _last_week() -> AnalyticsPeriodQueryDto:
    today_start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)
    return AnalyticsPeriodQueryDto(
        period_from=today_start - timedelta(days=6), period_to=today_start + timedelta(days=1)
    )


async def _register(
    user_repository: UserRepository, session: AsyncSession, telegram_id: int, days_ago: int
) -> int:
    user = await user_repository.create(CreateUserDto(name="u", telegram_id=telegram_id))
    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(created_at=datetime_now() - timedelta(days=days_ago))
    )
    return user.id


async def _pay(
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    *,
    user_id: int,
    plan_id: int,
    key: str,
    days_ago: int,
    final_price: Decimal = Decimal("500"),
    duration_days: int = 30,
) -> None:
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(
                user_id=user_id,
                plan_id=plan_id,
                idempotency_key=key,
                final_price=final_price,
                duration_days=duration_days,
            )
        )
    await transaction_repository.mark_status(order.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction)
        .where(Transaction.id == order.id)
        .values(updated_at=datetime_now() - timedelta(days=days_ago))
    )


async def test_actor_without_analytics_view_is_denied(
    pricing_repository: PricingRepository, session: AsyncSession, uow: UnitOfWork
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})

    with pytest.raises(PermissionDeniedError):
        await _use_case(session, pricing_repository, uow)(actor, AnalyticsPeriodQueryDto())


async def test_kpi_against_seeded_fixtures(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    payer = await user_repository.create(CreateUserDto(name="Payer", telegram_id=840_001))
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="analytics-kpi-1")
        )
    await transaction_repository.mark_status(order.id, TransactionStatus.PAID)

    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=840_002,
        remnawave_user_id=840_002,
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime_now() + timedelta(days=30),
        price_paid=Decimal("300"),
        currency=Currency.RUB,
        duration_days=30,
    )

    analytics = await _use_case(session, pricing_repository, uow)(OWNER, _last_week())

    assert analytics.snapshot.paid_subscriptions == 1
    assert analytics.snapshot.mrr == Decimal("300")
    assert analytics.current.payments == 1
    assert analytics.current.revenue == Decimal("500")
    assert analytics.revenue_by_currency == {Currency.RUB: Decimal("500")}
    assert analytics.current.paying_users == 1
    assert analytics.current.arppu == Decimal("500")


async def test_kpi_compares_with_the_previous_period(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    a = await _register(user_repository, session, 841_001, days_ago=30)
    b = await _register(user_repository, session, 841_002, days_ago=30)
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=a,
        plan_id=plan_id,
        key="cmp-a",
        days_ago=3,
        final_price=Decimal("500"),
    )
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=b,
        plan_id=plan_id,
        key="cmp-b-1",
        days_ago=10,
        final_price=Decimal("300"),
    )
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=b,
        plan_id=plan_id,
        key="cmp-b-2",
        days_ago=2,
        final_price=Decimal("300"),
    )

    analytics = await _use_case(session, pricing_repository, uow)(OWNER, _last_week())

    assert analytics.current.revenue == Decimal("800")
    assert analytics.current.paying_users == 2
    assert analytics.current.arppu == Decimal("400.00")
    assert analytics.current.new_payers == 1  # A; B first paid in the previous period
    assert analytics.previous.revenue == Decimal("300")
    assert analytics.previous.new_payers == 1
    assert analytics.period.previous_end == analytics.period.start


async def test_empty_period_returns_zeros(
    pricing_repository: PricingRepository, session: AsyncSession, uow: UnitOfWork
) -> None:
    analytics = await _use_case(session, pricing_repository, uow)(OWNER, AnalyticsPeriodQueryDto())

    assert analytics.current.revenue == Decimal(0) and analytics.current.arppu == Decimal(0)
    assert analytics.current.conversion_rate == 0.0 and analytics.current.churn_rate == 0.0
    assert analytics.revenue_by_currency == {}


async def test_churn_uses_payment_coverage(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    c = await _register(user_repository, session, 842_001, days_ago=60)
    d = await _register(user_repository, session, 842_002, days_ago=60)
    # covered 40..10 days ago: in at the start of a 30-day period, out at its end
    await _pay(
        transaction_repository, session, uow, user_id=c, plan_id=plan_id, key="ch-c", days_ago=40
    )
    # covered from 20 days ago, renewed early: not in the base, never churned
    await _pay(
        transaction_repository, session, uow, user_id=d, plan_id=plan_id, key="ch-d1", days_ago=20
    )
    await _pay(
        transaction_repository, session, uow, user_id=d, plan_id=plan_id, key="ch-d2", days_ago=2
    )

    analytics = await _use_case(session, pricing_repository, uow)(OWNER, AnalyticsPeriodQueryDto())

    assert analytics.current.churn_base == 1
    assert analytics.current.churned == 1
    assert analytics.current.churn_rate == pytest.approx(1.0)


async def test_mrr_is_rounded_to_cents(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=840_101,
        remnawave_user_id=840_101,
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime_now() + timedelta(days=90),
        price_paid=Decimal("100"),
        currency=Currency.RUB,
        duration_days=90,
    )

    analytics = await _use_case(session, pricing_repository, uow)(OWNER, _last_week())

    # 100 / 90 * 30 = 33.333...; unrounded, the API ships all ~28 digits
    assert analytics.snapshot.mrr == Decimal("33.33")


async def test_mrr_counts_limited_and_skips_trials(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=840_501,
        remnawave_user_id=840_501,
        status=SubscriptionStatus.LIMITED,
        price_paid=Decimal("300"),
        currency=Currency.RUB,
        duration_days=30,
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=840_502,
        remnawave_user_id=840_502,
        status=SubscriptionStatus.ACTIVE,
        is_trial=True,
        price_paid=Decimal("999"),
        currency=Currency.RUB,
        duration_days=30,
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=840_503,
        remnawave_user_id=840_503,
        status=SubscriptionStatus.ACTIVE,
        is_trial=True,
        price_paid=Decimal("999"),
        currency=Currency.RUB,
        duration_days=30,
    )

    analytics = await _use_case(session, pricing_repository, uow)(OWNER, _last_week())

    assert analytics.snapshot.mrr == Decimal("300")
    assert analytics.snapshot.paid_subscriptions == 1
    assert analytics.snapshot.limited_subscriptions == 1
    assert analytics.snapshot.active_trials == 2


async def test_conversion_counts_payment_within_7_days_of_mature_registrations(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    fast = await _register(user_repository, session, 840_601, days_ago=20)
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=fast,
        plan_id=plan_id,
        key="conv-fast",
        days_ago=18,
    )
    slow = await _register(user_repository, session, 840_602, days_ago=20)
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=slow,
        plan_id=plan_id,
        key="conv-slow",
        days_ago=5,
    )
    await _register(user_repository, session, 840_603, days_ago=20)
    too_fresh = await _register(user_repository, session, 840_604, days_ago=2)
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=too_fresh,
        plan_id=plan_id,
        key="conv-fresh",
        days_ago=1,
    )

    analytics = await _use_case(session, pricing_repository, uow)(OWNER, AnalyticsPeriodQueryDto())

    assert analytics.conversion_window_days == 7
    assert analytics.current.conversion_cohort == 3
    assert analytics.current.converted == 1
    assert analytics.current.conversion_rate == pytest.approx(1 / 3)


async def test_week_conversion_takes_registrations_from_the_shifted_window(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    payer = await _register(user_repository, session, 840_701, days_ago=9)
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=payer,
        plan_id=plan_id,
        key="conv-week",
        days_ago=6,
    )

    analytics = await _use_case(session, pricing_repository, uow)(OWNER, _last_week())

    assert analytics.current.conversion_cohort == 1
    assert analytics.current.converted == 1


async def test_conversion_window_boundaries_are_inclusive(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    # registered exactly 7 days ago, paid today: day-diff 7
    on_edge = await _register(user_repository, session, 840_801, days_ago=7)
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=on_edge,
        plan_id=plan_id,
        key="conv-edge-7",
        days_ago=0,
    )
    late = await _register(user_repository, session, 840_802, days_ago=10)
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=late,
        plan_id=plan_id,
        key="conv-edge-8",
        days_ago=2,
    )
    # registered 6 days ago: not mature yet
    await _register(user_repository, session, 840_803, days_ago=6)

    analytics = await _use_case(session, pricing_repository, uow)(OWNER, _last_week())

    assert analytics.current.conversion_cohort == 2
    assert analytics.current.converted == 1

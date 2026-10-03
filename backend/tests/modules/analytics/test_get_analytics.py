from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.subscription import Subscription
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
from app.modules.analytics.dto import GetAnalyticsDto
from app.modules.analytics.usecases import GetAnalyticsUseCase
from app.modules.pricing.repository import PricingRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.stats_repository import UserStatsRepository
from tests.modules.subscriptions.factories import create_subscription, make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _paid_order_dto(
    *, user_id: int, plan_id: int, idempotency_key: str, final_price: Decimal = Decimal("500")
) -> CreateTransactionDto:
    return CreateTransactionDto(
        user_id=user_id,
        plan_id=plan_id,
        plan_snapshot=make_plan_snapshot(plan_id=plan_id),
        duration_days=30,
        currency=Currency.RUB,
        purchase_type=PurchaseType.NEW,
        target_subscription_id=None,
        gateway_type=PaymentGatewayType.YOOKASSA,
        base_price=final_price,
        discount_percent=0,
        discount_source=DiscountSource.NONE,
        final_price=final_price,
        customer_email=None,
        idempotency_key=idempotency_key,
        expires_at=datetime_now() + timedelta(minutes=30),
    )


def _use_case(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
) -> GetAnalyticsUseCase:
    return GetAnalyticsUseCase(
        UserStatsRepository(user_repository.session),
        SubscriptionStatsRepository(subscription_repository.session),
        transaction_repository,
        pricing_repository,
        uow,
    )


async def test_actor_without_analytics_view_is_denied(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})
    use_case = _use_case(
        user_repository, subscription_repository, transaction_repository, pricing_repository, uow
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(actor, GetAnalyticsDto(days=7))


async def test_kpi_against_seeded_fixtures(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
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

    use_case = _use_case(
        user_repository, subscription_repository, transaction_repository, pricing_repository, uow
    )
    analytics = await use_case(OWNER, GetAnalyticsDto(days=7))

    assert analytics.kpi.active_subscriptions == 1
    assert analytics.kpi.paid_orders_count == 1
    assert analytics.kpi.total_revenue_by_currency.get(Currency.RUB, Decimal(0)) >= Decimal("500")
    assert analytics.kpi.mrr == Decimal("300")
    assert analytics.kpi.arpu == analytics.kpi.total_revenue_by_currency[Currency.RUB]


async def test_mrr_is_rounded_to_cents(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
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

    use_case = _use_case(
        user_repository, subscription_repository, transaction_repository, pricing_repository, uow
    )
    analytics = await use_case(OWNER, GetAnalyticsDto(days=7))

    # 100 / 90 * 30 = 33.333...; unrounded, the API ships all ~28 digits
    assert analytics.kpi.mrr == Decimal("33.33")


async def test_churn_snapshot_matches_the_repository_formula(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    retained = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=840_101,
        remnawave_user_id=840_101,
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime_now() + timedelta(days=60),
    )
    await session.execute(
        update(Subscription)
        .where(Subscription.id == retained.id)
        .values(created_at=datetime_now() - timedelta(days=60))
    )
    churned = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=840_102,
        remnawave_user_id=840_102,
        status=SubscriptionStatus.EXPIRED,
        expire_at=datetime_now() + timedelta(days=1),
    )
    await session.execute(
        update(Subscription)
        .where(Subscription.id == churned.id)
        .values(created_at=datetime_now() - timedelta(days=60))
    )
    # created inside the window, must be excluded
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=840_103,
        remnawave_user_id=840_103,
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime_now() + timedelta(days=30),
    )

    use_case = _use_case(
        user_repository, subscription_repository, transaction_repository, pricing_repository, uow
    )
    analytics = await use_case(OWNER, GetAnalyticsDto(days=7))

    assert analytics.churn.prev_active == 2
    assert analytics.churn.still_active == 1
    assert analytics.churn.churned == 1
    assert analytics.churn.churn_rate == pytest.approx(0.5)
    assert analytics.churn.retention_rate == pytest.approx(0.5)


async def test_all_time_period_clamps_churn_window_to_30_days(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
) -> None:
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=840_301,
        remnawave_user_id=840_301,
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime_now() + timedelta(days=30),
    )

    use_case = _use_case(
        user_repository, subscription_repository, transaction_repository, pricing_repository, uow
    )
    analytics = await use_case(OWNER, GetAnalyticsDto(days=0))

    assert analytics.churn.window_days == 30


async def test_conversion_rate_counts_only_in_window_registrations_with_a_paid_order(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    converted = await user_repository.create(CreateUserDto(name="Converted", telegram_id=840_201))
    async with uow:
        order = await transaction_repository.create(
            _paid_order_dto(
                user_id=converted.id, plan_id=plan_id, idempotency_key="analytics-conv-1"
            )
        )
    await transaction_repository.mark_status(order.id, TransactionStatus.PAID)

    await user_repository.create(CreateUserDto(name="NotConverted", telegram_id=840_202))

    outside_window = await user_repository.create(
        CreateUserDto(name="OldPayer", telegram_id=840_203)
    )
    await session.execute(
        update(User)
        .where(User.id == outside_window.id)
        .values(created_at=datetime_now() - timedelta(days=30))
    )
    async with uow:
        old_order = await transaction_repository.create(
            _paid_order_dto(
                user_id=outside_window.id, plan_id=plan_id, idempotency_key="analytics-conv-2"
            )
        )
    await transaction_repository.mark_status(old_order.id, TransactionStatus.PAID)

    use_case = _use_case(
        user_repository, subscription_repository, transaction_repository, pricing_repository, uow
    )
    analytics = await use_case(OWNER, GetAnalyticsDto(days=7))

    assert analytics.kpi.registered_in_period == 2
    assert analytics.kpi.paid_in_period == 1
    assert analytics.kpi.conversion_rate == pytest.approx(0.5)

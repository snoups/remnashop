from datetime import timedelta
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.payment_order import PaymentOrder
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    Locale,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
    Role,
    SubscriptionStatus,
)
from app.core.utils.time import datetime_now
from app.modules.overview.dto import GetOverviewDto
from app.modules.overview.usecases import GetOverviewUseCase
from app.modules.payments.dto import CreatePaymentOrderDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.pricing.repository import PricingRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import create_subscription, make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _paid_order_dto(*, user_id: int, plan_id: int, idempotency_key: str) -> CreatePaymentOrderDto:
    return CreatePaymentOrderDto(
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
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
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
    )
    async with uow:
        order = await payment_order_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="overview-owner-1")
        )
    await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)

    use_case = GetOverviewUseCase(
        user_repository, subscription_repository, payment_order_repository, pricing_repository
    )
    overview = await use_case(OWNER, GetOverviewDto(days=7))

    assert overview.users is not None
    assert overview.users.total >= 1
    assert overview.subscriptions is not None
    assert overview.subscriptions.active >= 1
    assert overview.payments is not None
    assert overview.payments.paid_orders_count >= 1
    assert overview.payments.revenue_by_currency.get(Currency.RUB, Decimal(0)) >= Decimal("500")


async def test_actor_missing_payments_view_gets_payments_none_but_keeps_other_sections(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
) -> None:
    actor = OWNER.model_copy(update={"permission_revokes": ["PAYMENTS_VIEW"]})

    use_case = GetOverviewUseCase(
        user_repository, subscription_repository, payment_order_repository, pricing_repository
    )
    overview = await use_case(actor, GetOverviewDto(days=7))

    assert overview.payments is None
    assert overview.users is not None
    assert overview.subscriptions is not None


async def test_days_window_excludes_orders_paid_before_the_cutoff(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    payer = await user_repository.create(CreateUserDto(name="OldPayer", telegram_id=830_101))
    async with uow:
        old_order = await payment_order_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="overview-old-1")
        )
    await payment_order_repository.mark_status(old_order.id, PaymentOrderStatus.PAID)
    # updated_at is a server default -- backdate this order outside the
    # usecase's own `days=7` window (same idiom as the Task 1/3 cutoff
    # tests) so this genuinely proves exclusion, not just inclusion.
    await session.execute(
        update(PaymentOrder)
        .where(PaymentOrder.id == old_order.id)
        .values(updated_at=datetime_now() - timedelta(days=10))
    )

    use_case = GetOverviewUseCase(
        user_repository, subscription_repository, payment_order_repository, pricing_repository
    )
    overview = await use_case(OWNER, GetOverviewDto(days=7))

    assert overview.payments is not None
    assert overview.payments.paid_orders_count == 0
    assert overview.payments.revenue_by_currency == {}


async def test_since_is_calendar_aligned_not_a_rolling_cutoff(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    payer = await user_repository.create(CreateUserDto(name="TodayPayer", telegram_id=830_201))
    async with uow:
        order = await payment_order_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="overview-today-1")
        )
    await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)
    # Backdate to 30 minutes into today (not yesterday) -- a rolling
    # `now - 1 day` cutoff would still include this, so this alone doesn't
    # distinguish the two window semantics. What does: with days=1, a
    # calendar-aligned `since` is midnight today, so an order backdated to
    # yesterday just before midnight must be excluded, while one backdated
    # to just after midnight today must be included.
    today_start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)
    await session.execute(
        update(PaymentOrder)
        .where(PaymentOrder.id == order.id)
        .values(updated_at=today_start + timedelta(minutes=30))
    )
    payer2 = await user_repository.create(CreateUserDto(name="YesterdayPayer", telegram_id=830_202))
    async with uow:
        old_order = await payment_order_repository.create(
            _paid_order_dto(
                user_id=payer2.id, plan_id=plan_id, idempotency_key="overview-yesterday-1"
            )
        )
    await payment_order_repository.mark_status(old_order.id, PaymentOrderStatus.PAID)
    await session.execute(
        update(PaymentOrder)
        .where(PaymentOrder.id == old_order.id)
        .values(updated_at=today_start - timedelta(minutes=30))
    )

    use_case = GetOverviewUseCase(
        user_repository, subscription_repository, payment_order_repository, pricing_repository
    )
    overview = await use_case(OWNER, GetOverviewDto(days=1))

    assert overview.payments is not None
    assert overview.payments.paid_orders_count == 1

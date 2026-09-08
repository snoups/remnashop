from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    Locale,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
    Role,
)
from app.core.exceptions import PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.analytics.usecases import GetLtvDistributionUseCase
from app.modules.payments.dto import CreatePaymentOrderDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.pricing.repository import PricingRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _paid_order_dto(
    *, user_id: int, plan_id: int, idempotency_key: str, final_price: Decimal
) -> CreatePaymentOrderDto:
    return CreatePaymentOrderDto(
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


async def test_actor_without_analytics_view_is_denied(
    payment_order_repository: PaymentOrderRepository, pricing_repository: PricingRepository
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})
    use_case = GetLtvDistributionUseCase(payment_order_repository, pricing_repository)

    with pytest.raises(PermissionDeniedError):
        await use_case(actor)


async def test_ltv_distribution_excludes_never_paid_users_and_buckets_by_total_spend(
    user_repository: UserRepository,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    low_spender = await user_repository.create(CreateUserDto(name="Low", telegram_id=830_301))
    high_spender = await user_repository.create(CreateUserDto(name="High", telegram_id=830_302))
    await user_repository.create(CreateUserDto(name="NeverPaid", telegram_id=830_303))

    async with uow:
        low_order = await payment_order_repository.create(
            _paid_order_dto(
                user_id=low_spender.id,
                plan_id=plan_id,
                idempotency_key="ltv-1",
                final_price=Decimal("100"),
            )
        )
        high_order = await payment_order_repository.create(
            _paid_order_dto(
                user_id=high_spender.id,
                plan_id=plan_id,
                idempotency_key="ltv-2",
                final_price=Decimal("900"),
            )
        )
    await payment_order_repository.mark_status(low_order.id, PaymentOrderStatus.PAID)
    await payment_order_repository.mark_status(high_order.id, PaymentOrderStatus.PAID)

    use_case = GetLtvDistributionUseCase(payment_order_repository, pricing_repository)
    distribution = await use_case(OWNER)

    total_bucketed_users = sum(bucket.users for bucket in distribution.buckets)
    assert total_bucketed_users == 2
    assert len(distribution.buckets) >= 1
    assert distribution.buckets[0].lower_bound == Decimal("100")
    assert distribution.buckets[-1].upper_bound is None


async def test_ltv_distribution_dedupes_boundaries_when_totals_share_the_same_value(
    user_repository: UserRepository,
    payment_order_repository: PaymentOrderRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    for i in range(5):
        payer = await user_repository.create(
            CreateUserDto(name=f"Payer{i}", telegram_id=830_310 + i)
        )
        async with uow:
            order = await payment_order_repository.create(
                _paid_order_dto(
                    user_id=payer.id,
                    plan_id=plan_id,
                    idempotency_key=f"ltv-dup-{i}",
                    final_price=Decimal("500"),
                )
            )
        await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)

    use_case = GetLtvDistributionUseCase(payment_order_repository, pricing_repository)
    distribution = await use_case(OWNER)

    assert len(distribution.buckets) == 1
    assert distribution.buckets[0].users == 5
    assert distribution.buckets[0].lower_bound == Decimal("500")

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.modules.analytics.usecases import GetCohortRetentionUseCase
from app.modules.payments.dto import CreatePaymentOrderDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot

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


async def test_actor_without_analytics_view_is_denied(
    user_repository: UserRepository,
    payment_order_repository: PaymentOrderRepository,
    uow: UnitOfWork,
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})
    use_case = GetCohortRetentionUseCase(user_repository, payment_order_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(actor)


async def test_cohort_retention_month_zero_vs_month_one(
    user_repository: UserRepository,
    payment_order_repository: PaymentOrderRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    # Both users registered "now" (this calendar month = cohort month 0).
    payer = await user_repository.create(CreateUserDto(name="Payer", telegram_id=829_001))
    await user_repository.create(CreateUserDto(name="NonPayer", telegram_id=829_002))

    async with uow:
        order = await payment_order_repository.create(
            _paid_order_dto(user_id=payer.id, plan_id=plan_id, idempotency_key="cohort-1")
        )
    await payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)
    # updated_at is a server default -- this order lands in the current
    # calendar month, proving month-0 retention without needing to backdate.

    use_case = GetCohortRetentionUseCase(user_repository, payment_order_repository, uow)
    result = await use_case(OWNER)

    current_month_key = datetime_now().strftime("%Y-%m")
    row = next(r for r in result.cohorts if r.cohort == current_month_key)
    assert row.cohort_size == 2
    assert row.retention_by_month[0] == pytest.approx(0.5)


async def test_cohort_retention_earliest_since_is_timezone_aware(
    user_repository: UserRepository,
    payment_order_repository: PaymentOrderRepository,
    uow: UnitOfWork,
) -> None:
    captured: dict[str, datetime] = {}
    original = user_repository.list_id_and_registration_date_since

    async def _spy(since: datetime, role: Role) -> list[tuple[int, date]]:
        captured["since"] = since
        return await original(since, role)

    user_repository.list_id_and_registration_date_since = _spy  # type: ignore[method-assign]

    use_case = GetCohortRetentionUseCase(user_repository, payment_order_repository, uow)
    await use_case(OWNER)

    assert captured["since"].tzinfo is not None

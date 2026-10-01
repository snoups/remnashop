from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.modules.analytics.dto import GetFunnelDto
from app.modules.analytics.usecases import GetFunnelUseCase
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


def _use_case(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> GetFunnelUseCase:
    return GetFunnelUseCase(user_repository, subscription_repository, transaction_repository, uow)


async def test_actor_without_analytics_view_is_denied(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})
    use_case = _use_case(user_repository, subscription_repository, transaction_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(actor, GetFunnelDto(days=7))


async def test_funnel_counts_are_independent_within_the_registered_cohort(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    # trial_then_paid: registered in window, took a trial, paid twice (repeat).
    trial_then_paid = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=828_001,
        remnawave_user_id=828_001,
        status=SubscriptionStatus.ACTIVE,
        is_trial=True,
    )
    async with uow:
        first = await transaction_repository.create(
            _paid_order_dto(
                user_id=trial_then_paid.user_id, plan_id=plan_id, idempotency_key="funnel-1"
            )
        )
        second = await transaction_repository.create(
            _paid_order_dto(
                user_id=trial_then_paid.user_id, plan_id=plan_id, idempotency_key="funnel-2"
            )
        )
    await transaction_repository.mark_status(first.id, TransactionStatus.PAID)
    await transaction_repository.mark_status(second.id, TransactionStatus.PAID)

    # direct_payer: registered in window, no trial, paid once directly.
    direct_payer = await user_repository.create(CreateUserDto(name="Direct", telegram_id=828_002))
    async with uow:
        direct_order = await transaction_repository.create(
            _paid_order_dto(user_id=direct_payer.id, plan_id=plan_id, idempotency_key="funnel-3")
        )
    await transaction_repository.mark_status(direct_order.id, TransactionStatus.PAID)

    # registered_only: registered in window, no trial, never paid.
    await user_repository.create(CreateUserDto(name="RegisteredOnly", telegram_id=828_003))

    # outside_window: registered too long ago, must be excluded from every step.
    outside_window = await user_repository.create(CreateUserDto(name="Old", telegram_id=828_004))
    await session.execute(
        update(User)
        .where(User.id == outside_window.id)
        .values(created_at=datetime_now() - timedelta(days=30))
    )

    use_case = _use_case(user_repository, subscription_repository, transaction_repository, uow)
    funnel = await use_case(OWNER, GetFunnelDto(days=7))

    by_key = {step.key: step for step in funnel.steps}
    assert by_key["registered"].count == 3
    assert by_key["trial"].count == 1
    assert by_key["first_paid"].count == 2
    assert by_key["repeat_paid"].count == 1
    assert by_key["registered"].pct_of_start == pytest.approx(1.0)
    assert by_key["trial"].pct_of_start == pytest.approx(1 / 3)
    assert by_key["first_paid"].pct_of_start == pytest.approx(2 / 3)
    # first_paid (2) exceeding trial (1) is expected -- direct-to-paid users
    # count independently of the trial step, per the spec's confirmed semantics.
    assert by_key["first_paid"].pct_of_prev == pytest.approx(2.0)

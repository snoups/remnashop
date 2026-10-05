from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.promocode import PromocodeActivation
from app.core.db.models.transaction import Transaction
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    Locale,
    PaymentGatewayType,
    PromocodeRewardType,
    PromocodeStatus,
    PurchaseType,
    Role,
    TransactionStatus,
)
from app.core.exceptions import PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.analytics.dto import AnalyticsPeriodQueryDto
from app.modules.analytics.usecases import GetPromocodeStatsUseCase
from app.modules.pricing.repository import PricingRepository
from app.modules.promocodes.dto import CreatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.stats_repository import UserStatsRepository
from tests.modules.subscriptions.factories import make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _use_case(
    session: AsyncSession,
    promocodes: PromocodeRepository,
    pricing: PricingRepository,
    uow: UnitOfWork,
) -> GetPromocodeStatsUseCase:
    return GetPromocodeStatsUseCase(
        UserStatsRepository(session),
        promocodes,
        TransactionStatsRepository(session),
        pricing,
        uow,
    )


async def _pay(
    tx_repo: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    *,
    user_id: int,
    plan_id: int,
    base: str,
    final: str,
    discount_percent: int,
    key: str,
    at: datetime,
) -> None:
    async with uow:
        order = await tx_repo.create(
            CreateTransactionDto(
                user_id=user_id,
                plan_id=plan_id,
                plan_snapshot=make_plan_snapshot(plan_id=plan_id, name="Basic"),
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                target_subscription_id=None,
                gateway_type=PaymentGatewayType.YOOKASSA,
                base_price=Decimal(base),
                discount_percent=discount_percent,
                discount_source=DiscountSource.NONE,
                final_price=Decimal(final),
                anchor_base_price=Decimal(base),
                anchor_final_price=Decimal(final),
                customer_email=None,
                idempotency_key=key,
                expires_at=datetime_now() + timedelta(minutes=30),
            )
        )
    await tx_repo.mark_status(order.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction).where(Transaction.id == order.id).values(updated_at=at)
    )


async def _activate(
    promocodes: PromocodeRepository,
    session: AsyncSession,
    promocode_id: int,
    user_id: int,
    at: datetime,
) -> None:
    activation = await promocodes.claim_activation(promocode_id, user_id, None)
    await session.execute(
        update(PromocodeActivation)
        .where(PromocodeActivation.id == activation.id)
        .values(activated_at=at)
    )


async def test_actor_without_promocodes_view_is_denied(
    promocode_repository: PromocodeRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})

    with pytest.raises(PermissionDeniedError):
        await _use_case(session, promocode_repository, pricing_repository, uow)(
            actor, AnalyticsPeriodQueryDto()
        )


async def test_promocode_stats_discount_and_free_reward_conversion(
    user_repository: UserRepository,
    promocode_repository: PromocodeRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    now = datetime_now()
    payer = await user_repository.create(CreateUserDto(name="P", telegram_id=893_001))
    converts = await user_repository.create(CreateUserDto(name="C", telegram_id=893_002))
    idle = await user_repository.create(CreateUserDto(name="I", telegram_id=893_003))
    free = await promocode_repository.create(
        CreatePromocodeDto(code="FREEDAYS", reward_type=PromocodeRewardType.DURATION, reward=7)
    )
    discount = await promocode_repository.create(
        CreatePromocodeDto(
            code="OFF25", reward_type=PromocodeRewardType.PURCHASE_DISCOUNT, reward=25
        )
    )
    await promocode_repository.create(
        CreatePromocodeDto(code="UNUSED", reward_type=PromocodeRewardType.TRAFFIC, reward=5)
    )
    await _activate(promocode_repository, session, free.id, converts.id, now - timedelta(hours=3))
    await _activate(promocode_repository, session, free.id, idle.id, now - timedelta(hours=3))
    await _activate(promocode_repository, session, discount.id, payer.id, now - timedelta(hours=3))
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=payer.id,
        plan_id=plan_id,
        base="1000",
        final="750",
        discount_percent=25,
        key="pc-1",
        at=now - timedelta(hours=2),
    )
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=converts.id,
        plan_id=plan_id,
        base="400",
        final="400",
        discount_percent=0,
        key="pc-2",
        at=now - timedelta(hours=1),
    )

    stats = await _use_case(session, promocode_repository, pricing_repository, uow)(
        OWNER, AnalyticsPeriodQueryDto()
    )

    assert stats.activations == 3 and stats.codes_used == 2
    assert stats.discount_given == Decimal("250")
    assert stats.revenue_with_discount == Decimal("750")
    assert stats.revenue_share == 750 / 1150
    assert stats.free_reward_conversion == 0.5
    assert len(stats.by_reward_type) == 6
    counts = {row.reward_type: row.activations for row in stats.by_reward_type}
    assert counts[PromocodeRewardType.DURATION] == 2
    assert counts[PromocodeRewardType.PURCHASE_DISCOUNT] == 1
    assert counts[PromocodeRewardType.TRAFFIC] == 0
    assert [row.code for row in stats.codes] == ["FREEDAYS", "OFF25"]
    free_row, discount_row = stats.codes
    assert free_row.conversion_rate == 0.5
    assert free_row.revenue_after == Decimal("400")
    assert free_row.total_activations == 2 and free_row.status == PromocodeStatus.ACTIVE
    assert discount_row.conversion_rate is None
    assert discount_row.revenue_after == Decimal("750")


async def test_promocode_stats_on_an_empty_period_are_zero(
    promocode_repository: PromocodeRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=400)
    stats = await _use_case(session, promocode_repository, pricing_repository, uow)(
        OWNER, AnalyticsPeriodQueryDto(period_from=start, period_to=start + timedelta(days=1))
    )

    assert stats.activations == 0 and stats.codes_used == 0 and stats.codes == []
    assert stats.discount_given == 0 and stats.revenue_share == 0
    assert stats.free_reward_conversion == 0
    assert len(stats.by_reward_type) == 6

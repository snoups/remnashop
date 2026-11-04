from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest
from remnapy import RemnawaveSDK
from remnapy.models import NodeResponseDto

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    DiscountSource,
    Locale,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    Role,
    TransactionStatus,
)
from app.core.exceptions import PermissionDeniedError, RemnawavePanelUnavailableError
from app.core.utils.time import datetime_now
from app.modules.overview.usecases import GetNodesOverviewUseCase, GetRecapUseCase
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


class _PanelDown:
    async def get_all_nodes(self) -> list[NodeResponseDto]:
        raise RemnawavePanelUnavailableError("down")


def _use_case(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
) -> GetRecapUseCase:
    session = user_repository.session
    sdk = cast(RemnawaveSDK, SimpleNamespace(nodes=_PanelDown()))
    return GetRecapUseCase(
        UserStatsRepository(session),
        SubscriptionStatsRepository(session),
        TransactionStatsRepository(session),
        pricing_repository,
        GetNodesOverviewUseCase(sdk),
        uow,
    )


async def _pay(
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
    key: str,
) -> None:
    async with uow:
        order = await transaction_repository.create(
            CreateTransactionDto(
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
                idempotency_key=key,
                expires_at=datetime_now() + timedelta(minutes=30),
            )
        )
    await transaction_repository.mark_status(order.id, TransactionStatus.PAID)


async def test_recap_counts_the_shop_and_leaves_nodes_empty_when_the_panel_is_down(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    use_case = _use_case(user_repository, transaction_repository, pricing_repository, uow)
    before = await use_case(OWNER)

    buyer = await create_subscription(
        subscription_repository, user_repository, telegram_id=870_001, remnawave_user_id=870_001
    )
    await _pay(transaction_repository, uow, buyer.user_id, plan_id, "recap-1")
    await _pay(transaction_repository, uow, buyer.user_id, plan_id, "recap-2")
    await user_repository.create(CreateUserDto(name="Browser", telegram_id=870_002))

    recap = await use_case(OWNER)

    assert recap.customers == before.customers + 2
    assert recap.new_customers == before.new_customers + 2
    assert recap.payers == before.payers + 1
    assert recap.new_payers == before.new_payers + 1
    assert recap.transactions == before.transactions + 2
    assert recap.revenue_total == before.revenue_total + Decimal("1000")
    assert recap.month_revenue == before.month_revenue + Decimal("1000")
    assert recap.active_subscriptions == before.active_subscriptions + 1
    assert recap.nodes is None and recap.countries is None
    assert recap.since <= datetime_now().date()


async def test_recap_is_the_owners_alone(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
) -> None:
    admin = OWNER.model_copy(update={"id": 2, "role": Role.ADMIN})

    with pytest.raises(PermissionDeniedError):
        await _use_case(user_repository, transaction_repository, pricing_repository, uow)(admin)

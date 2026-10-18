from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.subscription import Subscription
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AdLinkChannel,
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
from app.core.utils.time import datetime_now
from app.modules.advertising.dto import CreateAdLinkDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.analytics.dto import AnalyticsPeriodQueryDto
from app.modules.analytics.sources import SourceKind
from app.modules.analytics.usecases import GetFunnelUseCase
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.stats_repository import UserStatsRepository
from tests.fakes.analytics_cache import PassThroughAnalyticsCache
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


def _use_case(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> GetFunnelUseCase:
    return GetFunnelUseCase(
        UserStatsRepository(user_repository.session),
        SubscriptionStatsRepository(subscription_repository.session),
        transaction_repository,
        AdLinkRepository(user_repository.session),
        ReferralRepository(user_repository.session),
        uow,
        PassThroughAnalyticsCache(),
    )


async def test_actor_without_analytics_view_is_denied(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    uow: UnitOfWork,
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})
    use_case = _use_case(user_repository, subscription_repository, transaction_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(actor, AnalyticsPeriodQueryDto())


async def _connect(session: AsyncSession, subscription_id: int) -> None:
    await session.execute(
        update(Subscription)
        .where(Subscription.id == subscription_id)
        .values(first_connected_at=datetime_now())
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
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key=key)
        )
    await transaction_repository.mark_status(order.id, TransactionStatus.PAID)


async def test_funnel_steps_are_nested(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    await user_repository.create(CreateUserDto(name="RegisteredOnly", telegram_id=828_101))
    connected_only = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=828_102,
        remnawave_user_id=828_102,
        is_trial=True,
    )
    await _connect(session, connected_only.id)
    # connected on a trial row that was later replaced -- still connected
    trial_payer = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=828_103,
        remnawave_user_id=828_103,
        status=SubscriptionStatus.DELETED,
        is_trial=True,
    )
    await _connect(session, trial_payer.id)
    await _pay(transaction_repository, uow, trial_payer.user_id, plan_id, "funnel-n1")
    repeat_payer = await create_subscription(
        subscription_repository, user_repository, telegram_id=828_104, remnawave_user_id=828_104
    )
    await _connect(session, repeat_payer.id)
    await _pay(transaction_repository, uow, repeat_payer.user_id, plan_id, "funnel-n2")
    await _pay(transaction_repository, uow, repeat_payer.user_id, plan_id, "funnel-n3")
    never_connected = await create_subscription(
        subscription_repository, user_repository, telegram_id=828_105, remnawave_user_id=828_105
    )
    await _pay(transaction_repository, uow, never_connected.user_id, plan_id, "funnel-n4")
    # registered before the window: excluded from every step
    outside_window = await create_subscription(
        subscription_repository, user_repository, telegram_id=828_106, remnawave_user_id=828_106
    )
    await _connect(session, outside_window.id)
    await _pay(transaction_repository, uow, outside_window.user_id, plan_id, "funnel-n5")
    await session.execute(
        update(User)
        .where(User.id == outside_window.user_id)
        .values(created_at=datetime_now() - timedelta(days=60))
    )

    use_case = _use_case(user_repository, subscription_repository, transaction_repository, uow)
    funnel = await use_case(OWNER, AnalyticsPeriodQueryDto())

    assert [step.key for step in funnel.steps] == [
        "registered",
        "connected",
        "first_paid",
        "repeat_paid",
    ]
    # a payer counts as connected even without a recorded connection
    assert [step.count for step in funnel.steps] == [5, 4, 3, 1]
    assert funnel.steps[2].pct_of_prev == pytest.approx(3 / 4)
    assert funnel.paid_via_trial == 1


async def test_funnel_by_source_splits_the_cohort(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    ad_links = AdLinkRepository(session)
    referrals = ReferralRepository(session)
    organic = await create_subscription(
        subscription_repository, user_repository, telegram_id=828_201, remnawave_user_id=828_201
    )
    referred = await create_subscription(
        subscription_repository, user_repository, telegram_id=828_202, remnawave_user_id=828_202
    )
    advertised = await create_subscription(
        subscription_repository, user_repository, telegram_id=828_203, remnawave_user_id=828_203
    )
    await _pay(transaction_repository, uow, organic.user_id, plan_id, "funnel-s1")
    await _pay(transaction_repository, uow, referred.user_id, plan_id, "funnel-s2")
    await _pay(transaction_repository, uow, advertised.user_id, plan_id, "funnel-s3")
    link = await ad_links.create(CreateAdLinkDto(name="Blogger", code="blogger-funnel"))
    await ad_links.create_attribution(
        ad_link_id=link.id, user_id=advertised.user_id, channel=AdLinkChannel.BOT
    )
    await referrals.create_referral(
        referrer_id=organic.user_id, referred_id=referred.user_id, level=1
    )

    use_case = _use_case(user_repository, subscription_repository, transaction_repository, uow)
    funnel = await use_case(OWNER, AnalyticsPeriodQueryDto())

    rows = {(row.source, row.ad_link_id): row for row in funnel.by_source}
    assert set(rows) == {
        (SourceKind.ORGANIC, None),
        (SourceKind.REFERRAL, None),
        (SourceKind.AD_LINK, link.id),
    }
    assert rows[(SourceKind.AD_LINK, link.id)].name == "Blogger"
    assert sum(row.registered for row in funnel.by_source) == funnel.steps[0].count == 3
    assert sum(row.paid for row in funnel.by_source) == funnel.steps[2].count == 3

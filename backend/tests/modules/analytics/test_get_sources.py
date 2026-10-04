from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.referral import Referral
from app.core.db.models.transaction import Transaction
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AdLinkChannel,
    Currency,
    DiscountSource,
    Locale,
    PaymentGatewayType,
    PurchaseType,
    ReferralRewardType,
    Role,
    TransactionStatus,
)
from app.core.exceptions import PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.advertising.dto import CreateAdLinkDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.analytics.dto import AnalyticsPeriodQueryDto
from app.modules.analytics.sources import SourceKind
from app.modules.analytics.usecases import GetSourcesUseCase
from app.modules.pricing.repository import PricingRepository
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.stats_repository import UserStatsRepository
from tests.modules.subscriptions.factories import create_subscription, make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _use_case(session: AsyncSession, pricing: PricingRepository, uow: UnitOfWork):
    return GetSourcesUseCase(
        UserStatsRepository(session),
        UserRepository(session),
        TransactionStatsRepository(session),
        AdLinkRepository(session),
        ReferralRepository(session),
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
    plan_name: str,
    price: str,
    key: str,
    at: datetime,
) -> None:
    async with uow:
        order = await tx_repo.create(
            CreateTransactionDto(
                user_id=user_id,
                plan_id=plan_id,
                plan_snapshot=make_plan_snapshot(plan_id=plan_id, name=plan_name),
                duration_days=30,
                currency=Currency.RUB,
                purchase_type=PurchaseType.NEW,
                target_subscription_id=None,
                gateway_type=PaymentGatewayType.YOOKASSA,
                base_price=Decimal(price),
                discount_percent=0,
                discount_source=DiscountSource.NONE,
                final_price=Decimal(price),
                customer_email=None,
                idempotency_key=key,
                expires_at=datetime_now() + timedelta(minutes=30),
            )
        )
    await tx_repo.mark_status(order.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction).where(Transaction.id == order.id).values(updated_at=at)
    )


async def test_actor_without_sources_view_is_denied(
    pricing_repository: PricingRepository, session: AsyncSession, uow: UnitOfWork
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})

    with pytest.raises(PermissionDeniedError):
        await _use_case(session, pricing_repository, uow)(actor, AnalyticsPeriodQueryDto())


async def test_sources_split_channels_links_and_referral_payback(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    now = datetime_now()
    organic_paying = await user_repository.create(CreateUserDto(name="O1", telegram_id=890_001))
    await user_repository.create(CreateUserDto(name="O2", telegram_id=890_002))
    linked = await user_repository.create(CreateUserDto(name="L", telegram_id=890_003))
    referrer = await user_repository.create(CreateUserDto(name="Boss", telegram_id=890_004))
    r1 = await user_repository.create(CreateUserDto(name="R1", telegram_id=890_005))
    r2 = await user_repository.create(CreateUserDto(name="R2", telegram_id=890_006))
    ad_links = AdLinkRepository(session)
    link = await ad_links.create(CreateAdLinkDto(name="Blogger", code="src-blogger"))
    await ad_links.create_attribution(
        ad_link_id=link.id, user_id=linked.id, channel=AdLinkChannel.BOT
    )
    referrals = ReferralRepository(session)
    edge = await referrals.create_referral(referrer_id=referrer.id, referred_id=r1.id, level=1)
    await referrals.create_referral(referrer_id=referrer.id, referred_id=r2.id, level=1)
    sub = await create_subscription(
        subscription_repository, user_repository, telegram_id=890_007, remnawave_user_id=890_007
    )
    await referrals.create_reward(
        referral_id=edge.id,
        referrer_id=referrer.id,
        subscription_id=sub.id,
        payment_key="p-1",
        type=ReferralRewardType.EXTRA_DAYS,
        amount=Decimal(7),
    )
    for uid, price, key in (
        (organic_paying.id, "500", "s-1"),
        (linked.id, "300", "s-2"),
        (r1.id, "200", "s-3"),
    ):
        await _pay(
            transaction_repository,
            session,
            uow,
            user_id=uid,
            plan_id=plan_id,
            plan_name="Basic",
            price=price,
            key=key,
            at=now - timedelta(hours=1),
        )

    sources = await _use_case(session, pricing_repository, uow)(OWNER, AnalyticsPeriodQueryDto())

    rows = {row.source: row for row in sources.channels}
    assert [row.source for row in sources.channels] == [
        SourceKind.ORGANIC,
        SourceKind.AD_LINK,
        SourceKind.REFERRAL,
    ]
    assert rows[SourceKind.ORGANIC].revenue >= Decimal("500")
    organic = next(
        row for row in sources.channels if row.source == SourceKind.ORGANIC and row.registrations
    )
    assert organic.conversion_rate == organic.payers / organic.registrations
    assert rows[SourceKind.AD_LINK].revenue == Decimal("300")
    assert rows[SourceKind.REFERRAL].revenue == Decimal("200")
    assert rows[SourceKind.REFERRAL].registrations == 2
    assert rows[SourceKind.REFERRAL].conversion_rate == 0.5
    assert rows[SourceKind.REFERRAL].revenue_per_payer == Decimal("200")
    assert [(r.ad_link_id, r.name, r.revenue) for r in sources.ad_links] == [
        (link.id, "Blogger", Decimal("300"))
    ]
    assert sources.referral.referred_revenue == Decimal("200")
    assert sources.referral.reward_days == 7 and sources.referral.reward_points == 0
    assert sources.referral.referrers == 1
    assert sources.referral.deep_levels_revenue_share == 0.0
    top = sources.top_referrers[0]
    assert (top.user_id, top.invited, top.paid, top.revenue, top.reward_days) == (
        referrer.id,
        2,
        1,
        Decimal("200"),
        7,
    )
    assert top.name == "Boss"


async def test_sources_on_an_empty_period_are_zero(
    pricing_repository: PricingRepository, session: AsyncSession, uow: UnitOfWork
) -> None:
    start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=400)
    sources = await _use_case(session, pricing_repository, uow)(
        OWNER, AnalyticsPeriodQueryDto(period_from=start, period_to=start + timedelta(days=1))
    )

    assert [row.registrations for row in sources.channels] == [0, 0, 0]
    assert all(row.conversion_rate == 0 and row.revenue == 0 for row in sources.channels)
    assert sources.ad_links == [] and sources.top_referrers == []
    assert sources.referral.referrers == 0 and sources.referral.deep_levels_revenue_share == 0


async def test_same_named_ad_links_stay_separate_rows(
    user_repository: UserRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    ad_links = AdLinkRepository(session)
    users = [
        await user_repository.create(CreateUserDto(name=f"U{i}", telegram_id=891_000 + i))
        for i in range(2)
    ]
    for i, user in enumerate(users):
        link = await ad_links.create(CreateAdLinkDto(name="Same", code=f"same-{i}"))
        await ad_links.create_attribution(
            ad_link_id=link.id, user_id=user.id, channel=AdLinkChannel.BOT
        )

    sources = await _use_case(session, pricing_repository, uow)(OWNER, AnalyticsPeriodQueryDto())

    same = [row for row in sources.ad_links if row.name == "Same"]
    assert len(same) == 2 and len({row.ad_link_id for row in same}) == 2


async def test_cohort_payer_after_period_end_counts_as_payer(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    now = datetime_now()
    user = await user_repository.create(CreateUserDto(name="Late", telegram_id=892_001))
    await session.execute(
        update(User).where(User.id == user.id).values(created_at=now - timedelta(days=10))
    )
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=user.id,
        plan_id=plan_id,
        plan_name="Basic",
        price="100",
        key="late-1",
        at=now - timedelta(days=1),
    )

    sources = await _use_case(session, pricing_repository, uow)(
        OWNER,
        AnalyticsPeriodQueryDto(
            period_from=now - timedelta(days=11), period_to=now - timedelta(days=5)
        ),
    )

    organic = next(row for row in sources.channels if row.source == SourceKind.ORGANIC)
    assert organic.registrations == 1 and organic.payers == 1
    assert organic.revenue == Decimal("100")


async def test_referral_payback_counts_all_referred_users_paying_in_period(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    now = datetime_now()
    referrer = await user_repository.create(CreateUserDto(name="Boss", telegram_id=893_001))
    old = await user_repository.create(CreateUserDto(name="Old", telegram_id=893_002))
    orphan = await user_repository.create(CreateUserDto(name="Orphan", telegram_id=893_003))
    await session.execute(
        update(User).where(User.id == old.id).values(created_at=now - timedelta(days=40))
    )
    referrals = ReferralRepository(session)
    await referrals.create_referral(referrer_id=referrer.id, referred_id=old.id, level=1)
    session.add(Referral(referrer_id=None, referred_id=orphan.id, level=1))
    await session.flush()
    for user, key in ((old, "ref-1"), (orphan, "ref-2")):
        await _pay(
            transaction_repository,
            session,
            uow,
            user_id=user.id,
            plan_id=plan_id,
            plan_name="Basic",
            price="100",
            key=key,
            at=now - timedelta(hours=1),
        )

    sources = await _use_case(session, pricing_repository, uow)(
        OWNER,
        AnalyticsPeriodQueryDto(period_from=now - timedelta(days=2), period_to=now),
    )

    assert sources.referral.referred_revenue == Decimal("200")
    assert sources.referral.referrers == 1
    top = next(row for row in sources.top_referrers if row.user_id == referrer.id)
    assert (top.invited, top.paid, top.revenue) == (0, 1, Decimal("100"))

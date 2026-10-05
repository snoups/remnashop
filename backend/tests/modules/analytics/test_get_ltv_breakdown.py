from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.transaction import Transaction
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    AdLinkChannel,
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
from app.modules.advertising.dto import CreateAdLinkDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.analytics.sources import SourceKind
from app.modules.analytics.usecases import GetLtvBreakdownUseCase
from app.modules.pricing.repository import PricingRepository
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.transactions.dto import CreateTransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _use_case(session: AsyncSession, pricing: PricingRepository, uow: UnitOfWork):
    return GetLtvBreakdownUseCase(
        TransactionStatsRepository(session),
        SubscriptionStatsRepository(session),
        UserRepository(session),
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
                anchor_base_price=Decimal(price),
                anchor_final_price=Decimal(price),
                customer_email=None,
                idempotency_key=key,
                expires_at=datetime_now() + timedelta(minutes=30),
            )
        )
    await tx_repo.mark_status(order.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction).where(Transaction.id == order.id).values(updated_at=at)
    )


async def test_actor_without_ltv_view_is_denied(
    pricing_repository: PricingRepository, session: AsyncSession, uow: UnitOfWork
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})

    with pytest.raises(PermissionDeniedError):
        await _use_case(session, pricing_repository, uow)(actor, None)


async def test_breakdown_groups_by_first_plan_and_source_and_ranks_top_payers(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    now = datetime_now()
    organic = await user_repository.create(
        CreateUserDto(name="Org", telegram_id=880_001, username="org")
    )
    referred = await user_repository.create(CreateUserDto(name="Ref", telegram_id=880_002))
    linked = await user_repository.create(CreateUserDto(name="Lnk", telegram_id=880_003))
    ad_links = AdLinkRepository(session)
    link = await ad_links.create(CreateAdLinkDto(name="Blogger", code="ltv-blogger"))
    await ad_links.create_attribution(
        ad_link_id=link.id, user_id=linked.id, channel=AdLinkChannel.BOT
    )
    await ReferralRepository(session).create_referral(
        referrer_id=organic.id, referred_id=referred.id, level=1
    )
    # organic: Basic 100 then Pro 300 (first plan Basic); referred: Pro 200; linked: Pro 600
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=organic.id,
        plan_id=plan_id,
        plan_name="Basic",
        price="100",
        key="b-1",
        at=now - timedelta(days=20),
    )
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=organic.id,
        plan_id=plan_id,
        plan_name="Pro",
        price="300",
        key="b-2",
        at=now - timedelta(days=10),
    )
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=referred.id,
        plan_id=plan_id,
        plan_name="Pro",
        price="200",
        key="b-3",
        at=now - timedelta(days=5),
    )
    await _pay(
        transaction_repository,
        session,
        uow,
        user_id=linked.id,
        plan_id=plan_id,
        plan_name="Pro",
        price="600",
        key="b-4",
        at=now - timedelta(days=3),
    )
    for user_id, name, days in ((linked.id, "Old", 5), (linked.id, "Newest", 40)):
        await subscription_repository.create(
            CreateSubscriptionDto(
                user_id=user_id,
                remnawave_user_id=880_100 + days,
                status=SubscriptionStatus.ACTIVE,
                is_trial=False,
                traffic_limit=100,
                device_limit=3,
                expire_at=now + timedelta(days=days),
                url=f"https://example.com/sub/{days}",
                plan_snapshot=make_plan_snapshot(name=name),
            )
        )

    result = await _use_case(session, pricing_repository, uow)(OWNER, None)

    assert [(g.key, g.source, g.customers, g.avg_ltv) for g in result.by_first_plan] == [
        ("Basic", None, 1, Decimal("400.00")),
        ("Pro", None, 2, Decimal("400.00")),
    ]
    assert [(g.key, g.source, g.customers, g.avg_ltv) for g in result.by_source] == [
        ("Blogger", SourceKind.AD_LINK, 1, Decimal("600.00")),
        ("organic", SourceKind.ORGANIC, 1, Decimal("400.00")),
        ("referral", SourceKind.REFERRAL, 1, Decimal("200.00")),
    ]
    assert [(p.user_id, p.spent, p.payments, p.current_plan) for p in result.top_payers] == [
        (linked.id, Decimal("600.00"), 1, "Newest"),
        (organic.id, Decimal("400.00"), 2, None),
        (referred.id, Decimal("200.00"), 1, None),
    ]
    assert result.top_payers[1].username == "org"
    assert result.top_payers[0].last_paid_at is not None


async def test_ad_link_named_like_a_source_stays_a_separate_group(
    user_repository: UserRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    now = datetime_now()
    organic = await user_repository.create(CreateUserDto(name="O", telegram_id=881_001))
    linked = await user_repository.create(CreateUserDto(name="L", telegram_id=881_002))
    ad_links = AdLinkRepository(session)
    link = await ad_links.create(CreateAdLinkDto(name="organic", code="ltv-organic-name"))
    await ad_links.create_attribution(
        ad_link_id=link.id, user_id=linked.id, channel=AdLinkChannel.BOT
    )
    for user, price, key in ((organic, "100", "n-1"), (linked, "300", "n-2")):
        await _pay(
            transaction_repository,
            session,
            uow,
            user_id=user.id,
            plan_id=plan_id,
            plan_name="Basic",
            price=price,
            key=key,
            at=now - timedelta(days=2),
        )

    result = await _use_case(session, pricing_repository, uow)(OWNER, None)

    assert [(g.key, g.source, g.customers, g.avg_ltv) for g in result.by_source] == [
        ("organic", SourceKind.AD_LINK, 1, Decimal("300.00")),
        ("organic", SourceKind.ORGANIC, 1, Decimal("100.00")),
    ]

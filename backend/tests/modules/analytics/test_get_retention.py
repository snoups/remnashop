from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.transaction import Transaction
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PurchaseType, Role, SubscriptionStatus, TransactionStatus
from app.core.exceptions import PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.analytics.coverage import is_covered
from app.modules.analytics.dto import ListExpiringCustomersDto
from app.modules.analytics.usecases import GetRetentionUseCase, ListExpiringCustomersUseCase
from app.modules.analytics.usecases.get_retention import (
    _anniversaries,
    _churn_probe,
    _monthly_churn,
)
from app.modules.pricing.repository import PricingRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.users.dto import UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.analytics_cache import PassThroughAnalyticsCache
from tests.modules.analytics.test_get_analytics import _paid_order_dto
from tests.modules.subscriptions.factories import create_subscription, make_plan_snapshot

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
NOW = datetime(2026, 6, 15, 12, tzinfo=UTC)


def _use_case(
    session: AsyncSession, pricing_repository: PricingRepository, uow: UnitOfWork
) -> GetRetentionUseCase:
    return GetRetentionUseCase(
        SubscriptionStatsRepository(session),
        TransactionStatsRepository(session),
        UserRepository(session),
        pricing_repository,
        uow,
        PassThroughAnalyticsCache(),
    )


def _list_use_case(session: AsyncSession, uow: UnitOfWork) -> ListExpiringCustomersUseCase:
    return ListExpiringCustomersUseCase(
        SubscriptionStatsRepository(session),
        TransactionStatsRepository(session),
        UserRepository(session),
        uow,
        PassThroughAnalyticsCache(),
    )


async def test_actor_without_expiring_view_is_denied(
    session: AsyncSession, uow: UnitOfWork
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})

    with pytest.raises(PermissionDeniedError):
        await _list_use_case(session, uow)(actor, ListExpiringCustomersDto(page=1, page_size=10))


def test_anniversaries_only_count_the_ones_already_passed() -> None:
    first_paid = {
        1: datetime(2026, 1, 1, tzinfo=UTC),
        2: datetime(2026, 1, 1, tzinfo=UTC),
        3: datetime(2026, 5, 20, tzinfo=UTC),
    }

    assert _anniversaries(first_paid, 1, NOW) == {
        1: datetime(2026, 2, 1, tzinfo=UTC),
        2: datetime(2026, 2, 1, tzinfo=UTC),
    }
    assert set(_anniversaries(first_paid, 3, NOW)) == {1, 2}
    assert _anniversaries(first_paid, 6, NOW) == {}


def _covered(
    coverage: dict[int, list[tuple[datetime, datetime]]], months: list[datetime]
) -> dict[datetime, set[int]]:
    points = {p for start in months for p in (start, _churn_probe(start, NOW))}
    return {p: {u for u, s in coverage.items() if is_covered(s, p)} for p in points}


def test_monthly_churn_counts_lapses_inside_each_month() -> None:
    may = datetime(2026, 5, 1, tzinfo=UTC)
    june = datetime(2026, 6, 1, tzinfo=UTC)
    coverage = {
        1: [(datetime(2026, 4, 1, tzinfo=UTC), datetime(2026, 5, 10, tzinfo=UTC))],
        2: [(datetime(2026, 4, 1, tzinfo=UTC), datetime(2026, 8, 1, tzinfo=UTC))],
        3: [(datetime(2026, 5, 20, tzinfo=UTC), datetime(2026, 6, 5, tzinfo=UTC))],
    }

    rows = _monthly_churn(_covered(coverage, [may, june]), [may, june], NOW)

    assert [r.month for r in rows] == ["2026-05", "2026-06"]
    assert (rows[0].base, rows[0].churned, rows[0].rate) == (2, 1, 0.5)
    # june base is user 2 and 3 (3 covered through 6/5); user 3 lapsed before now
    assert (rows[1].base, rows[1].churned, rows[1].rate) == (2, 1, 0.5)


def test_monthly_churn_without_base_is_zero() -> None:
    june = datetime(2026, 6, 1, tzinfo=UTC)
    rows = _monthly_churn(_covered({}, [june]), [june], NOW)

    assert (rows[0].base, rows[0].churned, rows[0].rate) == (0, 0, 0.0)


async def test_actor_without_retention_view_is_denied(
    pricing_repository: PricingRepository, session: AsyncSession, uow: UnitOfWork
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})

    with pytest.raises(PermissionDeniedError):
        await _use_case(session, pricing_repository, uow)(actor)


async def _pay(
    tx_repo: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
    key: str,
    at: datetime,
    purchase_type: PurchaseType = PurchaseType.NEW,
) -> None:
    async with uow:
        order = await tx_repo.create(
            replace(
                _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key=key),
                purchase_type=purchase_type,
            )
        )
    await tx_repo.mark_status(order.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction).where(Transaction.id == order.id).values(updated_at=at)
    )


async def test_retention_expiring_blocks(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    now = datetime_now()
    soon = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=870_001,
        remnawave_user_id=870_001,
        expire_at=now + timedelta(days=3, hours=1),
    )
    later = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=870_002,
        remnawave_user_id=870_002,
        expire_at=now + timedelta(days=20, hours=1),
    )
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=870_003,
        remnawave_user_id=870_003,
        is_trial=True,
        expire_at=now + timedelta(days=5),
    )
    await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=soon.user_id,
            remnawave_user_id=870_004,
            status=SubscriptionStatus.ACTIVE,
            is_trial=False,
            traffic_limit=100,
            device_limit=3,
            expire_at=now + timedelta(days=10, hours=1),
            url="https://example.com/sub/870004",
            plan_snapshot=make_plan_snapshot(name="Extra"),
        )
    )
    for user_id, tag, renew in ((soon.user_id, "a", 2), (later.user_id, "b", 0)):
        await _pay(
            transaction_repository, session, uow, user_id, plan_id, f"r-{tag}0",
            now - timedelta(days=60),
        )  # fmt: skip
        for i in range(renew):
            await _pay(
                transaction_repository, session, uow, user_id, plan_id, f"r-{tag}{i + 1}",
                now - timedelta(days=40 - i * 10), PurchaseType.RENEW,
            )  # fmt: skip

    result = await _use_case(session, pricing_repository, uow)(OWNER)

    assert result.expiring_paid == 3 and result.expiring_trials == 1
    weeks = {w.key: w.count for w in result.expiring_weeks}
    assert weeks == {"1_7": 1, "8_14": 1, "15_21": 1, "22_30": 0}
    top = await _list_use_case(session, uow)(OWNER, ListExpiringCustomersDto(page=1, page_size=10))
    assert [c.user_id for c in top.items] == [soon.user_id, later.user_id] and top.total == 2
    assert top.items[0].plan_names == [soon.plan_snapshot.name, "Extra"]
    assert top.items[0].expire_at == soon.expire_at
    assert top.items[0].renewals == 2 and top.items[1].renewals == 0
    assert top.items[0].spent > top.items[1].spent
    second = await _list_use_case(session, uow)(
        OWNER, ListExpiringCustomersDto(page=2, page_size=1)
    )
    assert [c.user_id for c in second.items] == [later.user_id] and second.total == 2
    assert result.active_by_plan[0].plan_name == "Basic" and result.active_by_plan[0].active >= 2
    assert len(result.points) == 3 and len(result.monthly_churn) == 12


async def test_expiring_top_leaves_out_staff(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    now = datetime_now()
    customer, staff = [
        await create_subscription(
            subscription_repository,
            user_repository,
            telegram_id=telegram_id,
            remnawave_user_id=telegram_id,
            expire_at=now + timedelta(days=3, hours=1),
        )
        for telegram_id in (870_101, 870_102)
    ]
    await session.execute(update(User).where(User.id == staff.user_id).values(role=Role.ADMIN))
    for user_id, key in ((customer.user_id, "st-1"), (staff.user_id, "st-2")):
        await _pay(
            transaction_repository, session, uow, user_id, plan_id, key, now - timedelta(days=60)
        )

    result = await _list_use_case(session, uow)(
        OWNER, ListExpiringCustomersDto(page=1, page_size=10)
    )

    assert [c.user_id for c in result.items] == [customer.user_id] and result.total == 1

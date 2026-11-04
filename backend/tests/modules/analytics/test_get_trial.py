from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.subscription import Subscription
from app.core.db.models.transaction import Transaction
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SubscriptionStatus, TransactionStatus
from app.core.exceptions import PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.analytics.dto import AnalyticsPeriodQueryDto
from app.modules.analytics.usecases import GetTrialUseCase
from app.modules.analytics.usecases.get_trial import _day_ranges, _time_to_pay_key, _trial_day_key
from app.modules.pricing.repository import PricingRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.stats_repository import TransactionStatsRepository
from app.modules.users.dto import UserDto
from app.modules.users.repository import UserRepository
from app.modules.users.stats_repository import UserStatsRepository
from tests.fakes.analytics_cache import PassThroughAnalyticsCache
from tests.modules.analytics.test_get_analytics import _paid_order_dto
from tests.modules.subscriptions.factories import create_subscription

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
T0 = datetime(2026, 1, 1, 12, tzinfo=UTC)


def _use_case(
    session: AsyncSession, pricing_repository: PricingRepository, uow: UnitOfWork
) -> GetTrialUseCase:
    return GetTrialUseCase(
        UserStatsRepository(session),
        UserRepository(session),
        SubscriptionStatsRepository(session),
        TransactionStatsRepository(session),
        pricing_repository,
        uow,
        PassThroughAnalyticsCache(),
    )


def _midnight() -> datetime:
    return datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)


@pytest.mark.parametrize(
    ("days", "expected"),
    [(0, "same_day"), (1, "1"), (2, "2_3"), (3, "2_3"), (4, "4_7"), (7, "4_7"), (8, "8_14"),
     (14, "8_14"), (15, "15_30"), (30, "15_30"), (31, "later"), (-1, "same_day")],
)  # fmt: skip
def test_time_to_pay_key_edges(days: int, expected: str) -> None:
    assert _time_to_pay_key(T0, T0 + timedelta(days=days, hours=1)) == expected


@pytest.mark.parametrize(
    ("hours", "expected"),
    [(1, "1"), (6 * 24 + 1, "7"), (7 * 24 + 1, "after_1_3"), (9 * 24 + 1, "after_1_3"),
     (10 * 24 + 1, "after_4_7"), (13 * 24 + 1, "after_4_7"),
     (14 * 24 + 1, "after_8_30"), (36 * 24 + 1, "after_8_30"),
     (37 * 24 + 1, "after_later")],
)  # fmt: skip
def test_trial_day_key_edges(hours: int, expected: str) -> None:
    assert _trial_day_key(T0, 7, T0 + timedelta(hours=hours)) == expected


async def _trial(
    sub_repo: SubscriptionRepository,
    user_repo: UserRepository,
    session: AsyncSession,
    tg: int,
    at: datetime,
    duration: int = 7,
) -> int:
    sub = await create_subscription(
        sub_repo,
        user_repo,
        telegram_id=tg,
        remnawave_user_id=tg,
        is_trial=True,
        duration_days=duration,
    )
    await session.execute(
        update(Subscription).where(Subscription.id == sub.id).values(created_at=at)
    )
    await session.execute(update(User).where(User.id == sub.user_id).values(created_at=at))
    return sub.user_id


async def _pay(
    tx_repo: TransactionRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    user_id: int,
    plan_id: int,
    key: str,
    at: datetime,
) -> None:
    async with uow:
        order = await tx_repo.create(
            _paid_order_dto(user_id=user_id, plan_id=plan_id, idempotency_key=key)
        )
    await tx_repo.mark_status(order.id, TransactionStatus.PAID)
    await session.execute(
        update(Transaction).where(Transaction.id == order.id).values(updated_at=at)
    )


async def test_actor_without_trial_view_is_denied(
    pricing_repository: PricingRepository, session: AsyncSession, uow: UnitOfWork
) -> None:
    actor = OWNER.model_copy(update={"role": Role.USER})

    with pytest.raises(PermissionDeniedError):
        await _use_case(session, pricing_repository, uow)(actor, AnalyticsPeriodQueryDto())


async def test_trial_conversion_buckets_and_plans(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    now = datetime_now()
    a = await _trial(
        subscription_repository, user_repository, session, 860_001, now - timedelta(days=20)
    )
    b = await _trial(
        subscription_repository, user_repository, session, 860_002, now - timedelta(days=15)
    )
    await _trial(
        subscription_repository, user_repository, session, 860_003, now - timedelta(days=5)
    )
    d = await create_subscription(
        subscription_repository, user_repository, telegram_id=860_004, remnawave_user_id=860_004
    )
    await session.execute(
        update(User).where(User.id == d.user_id).values(created_at=now - timedelta(days=10))
    )

    async def pay(uid: int, key: str, at: datetime) -> None:
        await _pay(transaction_repository, session, uow, uid, plan_id, key, at)

    await pay(a, "t-a1", now - timedelta(days=14) + timedelta(hours=1))
    await pay(a, "t-a2", now - timedelta(days=3))
    await pay(b, "t-b1", now - timedelta(days=15) + timedelta(days=9, hours=1))
    await pay(d.user_id, "t-d1", now - timedelta(days=10) + timedelta(hours=2))

    trial = await _use_case(session, pricing_repository, uow)(OWNER, AnalyticsPeriodQueryDto())

    assert trial.trials == 3 and trial.converted == 2
    assert trial.conversion_rate == pytest.approx(2 / 3)
    assert trial.trial_days == 7
    by_day = {x.key: x.count for x in trial.by_trial_day}
    assert by_day["7"] == 1 and by_day["after_1_3"] == 1
    assert len(trial.by_trial_day) == 7 + 4
    assert trial.revenue_from_converted == Decimal("1500")
    same_day = next(x for x in trial.time_to_first_payment if x.key == "same_day")
    assert same_day.direct == 1
    assert trial.plans_after_trial[0].key == "Basic"
    assert trial.plans_after_trial[0].payments == 2


async def test_trial_on_an_empty_period_is_zero(
    pricing_repository: PricingRepository, session: AsyncSession, uow: UnitOfWork
) -> None:
    start = _midnight() - timedelta(days=6)
    trial = await _use_case(session, pricing_repository, uow)(
        OWNER, AnalyticsPeriodQueryDto(period_from=start, period_to=start + timedelta(days=1))
    )

    assert trial.trials == 0 and trial.converted == 0 and trial.conversion_rate == 0
    # nobody took a trial before it either: nothing to compare with, not a 0% rate
    assert trial.previous_conversion_rate is None
    assert trial.median_days_to_pay == 0 and trial.trial_days == 7
    assert len(trial.by_trial_day) == 7 + 4
    assert all(x.count == 0 for x in trial.by_trial_day)
    assert trial.plans_after_trial == []


async def test_by_trial_day_extends_to_the_longest_trial(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    now = datetime_now()
    for tg in (861_001, 861_002):
        await _trial(
            subscription_repository, user_repository, session, tg, now - timedelta(days=20)
        )
    long_user = await _trial(
        subscription_repository, user_repository, session, 861_003, now - timedelta(days=20), 14
    )
    await _pay(
        transaction_repository, session, uow, long_user, plan_id, "x-1",
        now - timedelta(days=20) + timedelta(days=9, hours=1),
    )  # fmt: skip

    trial = await _use_case(session, pricing_repository, uow)(OWNER, AnalyticsPeriodQueryDto())

    assert trial.trial_days == 7
    assert [x.key for x in trial.by_trial_day] == [
        "1",
        "2",
        "3",
        "4_6",
        "7",
        "8_14",
        "after_1_3",
        "after_4_7",
        "after_8_30",
        "after_later",
    ]
    assert {x.key: x.count for x in trial.by_trial_day}["8_14"] == 1


async def test_previous_rate_median_time_to_pay_and_earliest_trial(
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    plan_id: int,
) -> None:
    now = datetime_now()

    async def pay(uid: int, key: str, at: datetime) -> None:
        await _pay(transaction_repository, session, uow, uid, plan_id, key, at)

    previous = await _trial(
        subscription_repository, user_repository, session, 862_001, now - timedelta(days=45)
    )
    await pay(previous, "p-1", now - timedelta(days=44))
    # paid 40 days into a 30-day-old comparison: later than the current cohort could have
    slow = await _trial(
        subscription_repository, user_repository, session, 862_006, now - timedelta(days=45)
    )
    await pay(slow, "p-5", now - timedelta(days=5))
    e1 = await _trial(
        subscription_repository, user_repository, session, 862_002, now - timedelta(days=20)
    )
    # a later trial row for the same user; the earliest one must define the cohort entry
    later = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=862_003,
        remnawave_user_id=862_003,
        status=SubscriptionStatus.DELETED,
        is_trial=True,
    )
    await session.execute(
        update(Subscription)
        .where(Subscription.id == later.id)
        .values(user_id=e1, created_at=now - timedelta(days=10))
    )
    e2 = await _trial(
        subscription_repository, user_repository, session, 862_004, now - timedelta(days=15)
    )
    direct = await create_subscription(
        subscription_repository, user_repository, telegram_id=862_005, remnawave_user_id=862_005
    )
    await session.execute(
        update(User).where(User.id == direct.user_id).values(created_at=now - timedelta(days=10))
    )
    await pay(e1, "p-2", now - timedelta(days=20) + timedelta(days=2, hours=1))
    await pay(e2, "p-3", now - timedelta(days=15) + timedelta(days=5, hours=1))
    await pay(direct.user_id, "p-4", now - timedelta(days=10) + timedelta(hours=2))

    trial = await _use_case(session, pricing_repository, uow)(OWNER, AnalyticsPeriodQueryDto())

    assert trial.trials == 2 and trial.converted == 2
    assert trial.previous_trials == 2
    assert trial.previous_conversion_rate == pytest.approx(0.5)
    assert trial.previous_revenue_from_converted > 0
    assert trial.previous_revenue_from_converted < trial.revenue_from_converted
    assert trial.median_days_to_pay == 3
    split = {x.key: (x.via_trial, x.direct) for x in trial.time_to_first_payment}
    assert split["2_3"] == (1, 0) and split["4_7"] == (1, 0) and split["same_day"] == (0, 1)


@pytest.mark.parametrize(
    ("longest", "trial_days", "expected"),
    [
        (7, 7, [(day, day) for day in range(1, 8)]),
        (3, 3, [(1, 1), (2, 2), (3, 3)]),
        (14, 7, [(1, 1), (2, 2), (3, 3), (4, 6), (7, 7), (8, 14)]),
        (10, 10, [(1, 1), (2, 2), (3, 3), (4, 7), (8, 9), (10, 10)]),
        (60, 30, [(1, 1), (2, 2), (3, 3), (4, 7), (8, 14), (15, 29), (30, 30), (31, 60)]),
        (30, 4, [(1, 1), (2, 2), (3, 3), (4, 4), (5, 7), (8, 14), (15, 30)]),
    ],
)
def test_day_ranges_group_a_long_trial_and_keep_its_last_day(
    longest: int, trial_days: int, expected: list[tuple[int, int]]
) -> None:
    assert _day_ranges(longest, trial_days) == expected

from collections import Counter
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from functools import partial
from typing import Final, Optional

from app.core.actor import Actor
from app.core.constants import ONE_CENT
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.analytics.aggregates import median
from app.modules.analytics.cache import AnalyticsCache
from app.modules.analytics.dto import (
    AnalyticsPeriodInfoDto,
    AnalyticsPeriodQueryDto,
    RevenueGroupDto,
    TimeToPayBucketDto,
    TrialDayBucketDto,
    TrialDto,
)
from app.modules.analytics.period import AnalyticsPeriod, resolve_period
from app.modules.pricing import PricingRepository
from app.modules.subscriptions import SubscriptionStatsRepository
from app.modules.transactions import PaidTransactionDto, TransactionStatsRepository
from app.modules.users import UserRepository, UserStatsRepository

_ZERO: Final[Decimal] = Decimal(0)
_DEFAULT_TRIAL_DAYS: Final[int] = 7
_AFTER_KEYS: Final[tuple[str, ...]] = ("after_1_3", "after_4_7", "after_8_30", "after_later")
_TIME_TO_PAY_KEYS: Final[tuple[str, ...]] = (
    "same_day",
    "1",
    "2_3",
    "4_7",
    "8_14",
    "15_30",
    "later",
)

_Cohort = list[tuple[int, datetime, int, Optional[PaidTransactionDto]]]


def _cents(value: Decimal) -> Decimal:
    return value.quantize(ONE_CENT, rounding=ROUND_HALF_UP)


def _trial_day_key(trial_start: datetime, trial_days: int, first_paid: datetime) -> str:
    day = (first_paid - trial_start).days + 1
    if day <= trial_days:
        return str(max(day, 1))
    past = day - trial_days
    if past <= 3:
        return "after_1_3"
    if past <= 7:
        return "after_4_7"
    if past <= 30:
        return "after_8_30"
    return "after_later"


def _time_to_pay_key(registered_at: datetime, first_paid: datetime) -> str:
    days = (first_paid - registered_at).days
    if days <= 0:
        return "same_day"
    if days == 1:
        return "1"
    if days <= 3:
        return "2_3"
    if days <= 7:
        return "4_7"
    if days <= 14:
        return "8_14"
    if days <= 30:
        return "15_30"
    return "later"


def _earliest_trials(rows: list[tuple[int, datetime, int]]) -> dict[int, tuple[datetime, int]]:
    earliest: dict[int, tuple[datetime, int]] = {}
    for user_id, started, duration in rows:
        if user_id not in earliest or started < earliest[user_id][0]:
            earliest[user_id] = (started, duration)
    return earliest


def _first_paid_after(
    paid: list[PaidTransactionDto], trials: dict[int, tuple[datetime, int]]
) -> dict[int, PaidTransactionDto]:
    first: dict[int, PaidTransactionDto] = {}
    for row in paid:  # sorted by paid_at
        trial = trials.get(row.user_id)
        if trial is not None and row.user_id not in first and row.paid_at > trial[0]:
            first[row.user_id] = row
    return first


def _most_common_duration(durations: list[int]) -> int:
    if not durations:
        return _DEFAULT_TRIAL_DAYS
    return Counter(durations).most_common(1)[0][0]


def _day_buckets(cohort: _Cohort, trial_days: int) -> list[TrialDayBucketDto]:
    counts = Counter(
        _trial_day_key(started, duration, first.paid_at)
        for _, started, duration, first in cohort
        if first is not None
    )
    longest = max([trial_days, *(duration for _, _, duration, _ in cohort)])
    keys = [*(str(day) for day in range(1, longest + 1)), *_AFTER_KEYS]
    return [TrialDayBucketDto(key=key, count=counts[key]) for key in keys]


def _plans_after_trial(cohort: _Cohort) -> list[RevenueGroupDto]:
    by_plan: dict[str, list[Decimal]] = {}
    for _, _, _, first in cohort:
        if first is not None:
            by_plan.setdefault(first.plan_name, []).append(first.anchor_final_price)
    rows = [
        RevenueGroupDto(key=name, payments=len(amounts), revenue=_cents(sum(amounts, start=_ZERO)))
        for name, amounts in by_plan.items()
    ]
    return sorted(rows, key=lambda row: row.revenue, reverse=True)


def _time_to_first_payment(
    first_paid: dict[int, datetime], registered: dict[int, datetime], via_trial: set[int]
) -> list[TimeToPayBucketDto]:
    via: Counter[str] = Counter()
    direct: Counter[str] = Counter()
    for user_id, paid_at in first_paid.items():
        if user_id in registered:
            key = _time_to_pay_key(registered[user_id], paid_at)
            (via if user_id in via_trial else direct)[key] += 1
    return [
        TimeToPayBucketDto(key=key, via_trial=via[key], direct=direct[key])
        for key in _TIME_TO_PAY_KEYS
    ]


class GetTrialUseCase(UseCase[AnalyticsPeriodQueryDto, TrialDto]):
    required_permission = Permission.ANALYTICS_TRIAL_VIEW

    def __init__(
        self,
        user_stats: UserStatsRepository,
        user_repository: UserRepository,
        subscription_stats: SubscriptionStatsRepository,
        transaction_stats: TransactionStatsRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        cache: AnalyticsCache,
    ) -> None:
        self._user_stats = user_stats
        self._user_repository = user_repository
        self._subscription_stats = subscription_stats
        self._transaction_stats = transaction_stats
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._cache = cache

    async def _cohort(
        self, period: AnalyticsPeriod, now: datetime
    ) -> tuple[_Cohort, list[PaidTransactionDto]]:
        trials = _earliest_trials(
            await self._subscription_stats.list_trials_started(period.start, period.end)
        )
        paid = await self._transaction_stats.list_paid_by_users(list(trials), now)
        first = _first_paid_after(paid, trials)
        cohort = [
            (user_id, started, duration, first.get(user_id))
            for user_id, (started, duration) in trials.items()
        ]
        return cohort, paid

    async def _new_payers(
        self, period: AnalyticsPeriod
    ) -> tuple[dict[int, datetime], dict[int, datetime], set[int]]:
        first_paid = await self._transaction_stats.first_paid_at(period.end, since=period.start)
        ids = list(first_paid)
        registered = {
            u.id: u.created_at
            for u in await self._user_repository.list_by_ids(ids)
            if u.created_at is not None
        }
        return first_paid, registered, await self._subscription_stats.list_user_ids_with_trial(ids)

    async def _execute(self, actor: Actor, data: AnalyticsPeriodQueryDto) -> TrialDto:
        return await self._cache.get_or_compute(
            "get_trial", data, TrialDto, partial(self._compute, data)
        )

    async def _compute(self, data: AnalyticsPeriodQueryDto) -> TrialDto:
        async with self._uow:
            now = datetime_now()
            period = resolve_period(
                data.period_from,
                data.period_to,
                earliest=await self._user_stats.earliest_registration(Role.USER),
                now=now,
            )
            rates = await self._pricing_repository.get_rate_table()
            cohort, paid = await self._cohort(period, now)
            previous, _ = await self._cohort(period.previous, now)
            first_paid, registered, via_trial = await self._new_payers(period)

            converted = [row for row in cohort if row[3] is not None]
            converted_ids = {row[0] for row in converted}
            trial_days = _most_common_duration([row[2] for row in cohort])
            previous_converted = sum(1 for row in previous if row[3] is not None)
            days_to_pay = [
                Decimal((first.paid_at - started).days)
                for _, started, _, first in converted
                if first is not None
            ]
            revenue = sum(
                (row.anchor_final_price for row in paid if row.user_id in converted_ids),
                start=_ZERO,
            )
            previous_range = period.previous
            return TrialDto(
                period=AnalyticsPeriodInfoDto(
                    start=period.start,
                    end=period.end,
                    previous_start=previous_range.start,
                    previous_end=previous_range.end,
                ),
                report_currency=rates.anchor,
                trials=len(cohort),
                converted=len(converted),
                conversion_rate=len(converted) / len(cohort) if cohort else 0.0,
                previous_conversion_rate=previous_converted / len(previous) if previous else 0.0,
                revenue_from_converted=_cents(revenue),
                median_days_to_pay=int(median(days_to_pay)),
                trial_days=trial_days,
                by_trial_day=_day_buckets(cohort, trial_days),
                time_to_first_payment=_time_to_first_payment(first_paid, registered, via_trial),
                plans_after_trial=_plans_after_trial(cohort),
            )

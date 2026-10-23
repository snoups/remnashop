from datetime import datetime, timedelta
from decimal import Decimal
from functools import partial
from typing import Final

from app.core.actor import Actor
from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.money import round_cents
from app.core.utils.time import datetime_now
from app.modules.analytics.aggregates import report_amount
from app.modules.analytics.cache import AnalyticsCache
from app.modules.analytics.coverage import shift_months
from app.modules.analytics.dto import (
    ExpiringCustomerDto,
    ExpiringWeekDto,
    MonthlyChurnDto,
    PlanActiveDto,
    RetentionDto,
    RetentionPointDto,
)
from app.modules.pricing import CurrencyRateTable, PricingRepository
from app.modules.subscriptions import LiveSubscriptionDto, SubscriptionStatsRepository
from app.modules.transactions import TransactionStatsRepository
from app.modules.users import UserRepository

_MICROSECOND: Final[timedelta] = timedelta(microseconds=1)
_ANNIVERSARIES: Final[tuple[int, ...]] = (1, 3, 6)
_CHURN_MONTHS: Final[int] = 12
_EXPIRING_DAYS: Final[int] = 30
_TOP_LIMIT: Final[int] = 10
_DAYS_PER_MONTH: Final[Decimal] = Decimal("30.44")
_WEEK_KEYS: Final[tuple[str, ...]] = ("1_7", "8_14", "15_21", "22_30")

_Segments = list[tuple[datetime, datetime]]


def _rate(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def _anniversaries(
    first_paid: dict[int, datetime], months: int, now: datetime
) -> dict[int, datetime]:
    # only payers whose anniversary has already come
    return {
        user_id: shift_months(at, months)
        for user_id, at in first_paid.items()
        if shift_months(at, months) <= now
    }


def _last_month_starts(now: datetime, count: int) -> list[datetime]:
    current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return [shift_months(current, offset) for offset in range(1 - count, 1)]


def _monthly_churn(
    covered: dict[datetime, set[int]], months: list[datetime], now: datetime
) -> list[MonthlyChurnDto]:
    rows: list[MonthlyChurnDto] = []
    for start in months:
        base = covered[start]
        churned = len(base - covered[_churn_probe(start, now)])
        rows.append(
            MonthlyChurnDto(
                month=start.strftime("%Y-%m"),
                base=len(base),
                churned=churned,
                rate=_rate(churned, len(base)),
            )
        )
    return rows


def _churn_probe(month_start: datetime, now: datetime) -> datetime:
    return min(shift_months(month_start, 1), now) - _MICROSECOND


def _week_key(expire_at: datetime, now: datetime) -> str:
    days = max((expire_at - now).days, 1)
    if days <= 7:
        return _WEEK_KEYS[0]
    if days <= 14:
        return _WEEK_KEYS[1]
    if days <= 21:
        return _WEEK_KEYS[2]
    return _WEEK_KEYS[3]


def _monthly_value(row: LiveSubscriptionDto, rates: CurrencyRateTable) -> Decimal:
    if row.duration_days <= 0:
        return ZERO_AMOUNT
    return report_amount(row.price_paid / row.duration_days * 30, row.currency, rates)


def _expiring_weeks(
    rows: list[LiveSubscriptionDto], now: datetime, rates: CurrencyRateTable
) -> list[ExpiringWeekDto]:
    counts = dict.fromkeys(_WEEK_KEYS, 0)
    at_risk = dict.fromkeys(_WEEK_KEYS, ZERO_AMOUNT)
    for row in rows:
        key = _week_key(row.expire_at, now)
        counts[key] += 1
        at_risk[key] += _monthly_value(row, rates)
    return [
        ExpiringWeekDto(key=key, count=counts[key], mrr_at_risk=round_cents(at_risk[key]))
        for key in _WEEK_KEYS
    ]


def _active_by_plan(live: list[LiveSubscriptionDto]) -> list[PlanActiveDto]:
    active: dict[str, int] = {}
    limited: dict[str, int] = {}
    for row in live:
        if row.is_trial:
            continue
        bucket = limited if row.status == SubscriptionStatus.LIMITED else active
        bucket[row.plan_name] = bucket.get(row.plan_name, 0) + 1
    rows = [
        PlanActiveDto(plan_name=name, active=active.get(name, 0), limited=limited.get(name, 0))
        for name in active.keys() | limited.keys()
    ]
    return sorted(rows, key=lambda row: (-row.active, row.plan_name))


class GetRetentionUseCase(UseCase[None, RetentionDto]):
    required_permission = Permission.ANALYTICS_RETENTION_VIEW

    def __init__(
        self,
        subscription_stats: SubscriptionStatsRepository,
        transaction_stats: TransactionStatsRepository,
        user_repository: UserRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        cache: AnalyticsCache,
    ) -> None:
        self._subscription_stats = subscription_stats
        self._transaction_stats = transaction_stats
        self._user_repository = user_repository
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._cache = cache

    async def _retention_points(
        self, first_paid: dict[int, datetime], now: datetime
    ) -> list[RetentionPointDto]:
        points: list[RetentionPointDto] = []
        for months in _ANNIVERSARIES:
            anniversaries = _anniversaries(first_paid, months, now)
            kept = await self._transaction_stats.users_covered_at_their_points(anniversaries, now)
            points.append(
                RetentionPointDto(
                    months=months,
                    rate=_rate(len(kept), len(anniversaries)),
                    eligible=len(anniversaries),
                )
            )
        return points

    async def _avg_paid_months(self, now: datetime) -> float:
        payers, days = await self._transaction_stats.total_covered_days(now)
        return days / payers / float(_DAYS_PER_MONTH) if payers else 0.0

    async def _top_customers(
        self, expiring: list[LiveSubscriptionDto], now: datetime
    ) -> list[ExpiringCustomerDto]:
        summaries = await self._transaction_stats.payer_summaries(
            now, user_ids={row.user_id for row in expiring}
        )
        spent = {s.user_id: s.spent for s in summaries}
        renewals = {s.user_id: s.renewals for s in summaries}
        nearest: dict[int, LiveSubscriptionDto] = {}
        for row in sorted(expiring, key=lambda r: r.expire_at):
            nearest.setdefault(row.user_id, row)
        top = sorted(
            nearest.values(), key=lambda r: spent.get(r.user_id, ZERO_AMOUNT), reverse=True
        )
        top = top[:_TOP_LIMIT]
        users = {u.id: u for u in await self._user_repository.list_by_ids([r.user_id for r in top])}
        return [
            ExpiringCustomerDto(
                user_id=row.user_id,
                name=users[row.user_id].name if row.user_id in users else "",
                username=users[row.user_id].username if row.user_id in users else None,
                plan_name=row.plan_name,
                expire_at=row.expire_at,
                spent=round_cents(spent.get(row.user_id, ZERO_AMOUNT)),
                renewals=renewals.get(row.user_id, 0),
            )
            for row in top
        ]

    async def _execute(self, actor: Actor, data: None) -> RetentionDto:
        return await self._cache.get_or_compute(
            "get_retention", data, RetentionDto, partial(self._compute, data)
        )

    async def _compute(self, data: None) -> RetentionDto:
        async with self._uow:
            now = datetime_now()
            rates = await self._pricing_repository.get_rate_table()
            first_paid = await self._transaction_stats.first_paid_at(now)
            months = _last_month_starts(now, _CHURN_MONTHS)
            covered = await self._transaction_stats.users_covered_at(
                {point for start in months for point in (start, _churn_probe(start, now))}, now
            )
            live = await self._subscription_stats.list_live()
            horizon = now + timedelta(days=_EXPIRING_DAYS)
            window = [row for row in live if now <= row.expire_at < horizon]
            expiring_paid = [row for row in window if not row.is_trial]
            return RetentionDto(
                report_currency=rates.anchor,
                points=await self._retention_points(first_paid, now),
                avg_paid_months=await self._avg_paid_months(now),
                expiring_paid=len(expiring_paid),
                expiring_trials=len(window) - len(expiring_paid),
                expiring_weeks=_expiring_weeks(expiring_paid, now, rates),
                expiring_top=await self._top_customers(expiring_paid, now),
                active_by_plan=_active_by_plan(live),
                monthly_churn=_monthly_churn(covered, months, now),
            )

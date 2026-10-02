import operator
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Final, Optional, TypeVar

from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role, SubscriptionStatus
from app.core.runtime_heartbeat import read_host_memory, read_runtime_heartbeats
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.overview.dto import (
    DailyAmountDto,
    DailyCountDto,
    GetOverviewDto,
    Granularity,
    HostMemoryDto,
    OverviewDto,
    OverviewOnlineDto,
    OverviewSubscriptionsDto,
    OverviewTransactionsDto,
    OverviewUsersDto,
    RuntimeProcessDto,
)
from app.modules.overview.online import read_daily_online_peaks, read_latest_online
from app.modules.pricing import PricingRepository, convert_for_report
from app.modules.subscriptions import SubscriptionStatsRepository
from app.modules.transactions import TransactionRepository
from app.modules.users import UserStatsRepository

_T = TypeVar("_T", int, Decimal)

# day below this span, monthly above -- weekly granularity skipped
# as a third code path nobody asked hard for.
_MONTHLY_THRESHOLD_DAYS: Final[int] = 90


def _iter_months(start: date, end: date) -> Iterator[date]:
    cur = start.replace(day=1)
    last = end.replace(day=1)
    while cur <= last:
        yield cur
        cur = (cur + timedelta(days=32)).replace(day=1)


def _bucketize(
    rows: list[tuple[date, _T]],
    start: date,
    end: date,
    granularity: Granularity,
    zero: _T,
    *,
    dense: bool,
    op: Callable[[_T, _T], _T] = operator.add,
) -> list[tuple[date, _T]]:
    if granularity == "month":
        acc: dict[date, _T] = dict.fromkeys(_iter_months(start, end), zero)
        for day, value in rows:
            key = day.replace(day=1)
            acc[key] = op(acc[key], value)
        return sorted(acc.items())
    if not dense:
        return rows
    acc = dict.fromkeys((start + timedelta(days=i) for i in range((end - start).days + 1)), zero)
    for day, value in rows:
        acc[day] = op(acc[day], value)
    return sorted(acc.items())


@dataclass(frozen=True, kw_only=True)
class _Period:
    today_start: datetime
    start_date: date
    today: date
    since: datetime
    granularity: Granularity
    dense: bool

    def bucketize(
        self,
        rows: list[tuple[date, _T]],
        zero: _T,
        op: Callable[[_T, _T], _T] = operator.add,
    ) -> list[tuple[date, _T]]:
        return _bucketize(
            rows, self.start_date, self.today, self.granularity, zero, dense=self.dense, op=op
        )


class GetOverviewUseCase(UseCase[GetOverviewDto, OverviewDto]):
    # Every admin may call this -- gating happens per-section below, not at
    # the router/permission-check level, since no single Permission covers
    # "can see the overview page".
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        user_stats: UserStatsRepository,
        subscription_stats: SubscriptionStatsRepository,
        transaction_repository: TransactionRepository,
        pricing_repository: PricingRepository,
        redis: Redis,
        uow: UnitOfWork,
    ) -> None:
        self._user_stats = user_stats
        self._subscription_stats = subscription_stats
        self._transaction_repository = transaction_repository
        self._pricing_repository = pricing_repository
        self._redis = redis
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetOverviewDto) -> OverviewDto:
        perms = PermissionPolicy.effective_permissions(actor)
        async with self._uow:
            period = await self._period(data.days)
            users = await self._users(period) if Permission.USERS_VIEW in perms else None
            subscriptions = (
                await self._subscriptions(period)
                if Permission.SUBSCRIPTIONS_VIEW in perms
                else None
            )
            transactions = (
                await self._transactions(period) if Permission.TRANSACTIONS_VIEW in perms else None
            )

        return OverviewDto(
            days=data.days,
            granularity=period.granularity,
            users=users,
            subscriptions=subscriptions,
            transactions=transactions,
            runtime=await self._runtime(),
            host_memory=_host_memory(),
            online=await self._online(period),
        )

    async def _period(self, days: int) -> _Period:
        today_start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)
        today = today_start.date()
        if days == 0:
            first_registration = await self._user_stats.earliest_registration(Role.USER)
            start_date = first_registration or today
        else:
            start_date = today - timedelta(days=days - 1)
        span_days = (today - start_date).days + 1
        return _Period(
            today_start=today_start,
            start_date=start_date,
            today=today,
            # Calendar-aligned to match the frontend's fillDailySeries, which
            # builds exactly `days` UTC calendar days ending today -- a rolling
            # now - days cutoff would include a partial day at the start and
            # the daily series wouldn't sum to the period-scoped card numbers.
            since=today_start - timedelta(days=span_days - 1),
            granularity="month" if span_days > _MONTHLY_THRESHOLD_DAYS else "day",
            dense=days == 0,
        )

    async def _users(self, period: _Period) -> OverviewUsersDto:
        daily = await self._user_stats.count_registrations_by_day(period.since, Role.USER)
        return OverviewUsersDto(
            total=await self._user_stats.count_by_role(Role.USER),
            new_today=await self._user_stats.count_new_since(period.today_start, Role.USER),
            daily_registrations=[
                DailyCountDto(day=day, count=count) for day, count in period.bucketize(daily, 0)
            ],
        )

    async def _subscriptions(self, period: _Period) -> OverviewSubscriptionsDto:
        by_status = await self._subscription_stats.count_by_status()
        active = by_status.get(SubscriptionStatus.ACTIVE, 0)
        limited = by_status.get(SubscriptionStatus.LIMITED, 0)
        expired = by_status.get(SubscriptionStatus.EXPIRED, 0)
        return OverviewSubscriptionsDto(
            total=active + limited + expired,
            active=active,
            limited=limited,
            expired=expired,
            disabled=by_status.get(SubscriptionStatus.DISABLED, 0),
            expiring_soon=await self._subscription_stats.count_expiring_between(
                period.today_start, period.today_start + timedelta(days=7)
            ),
        )

    async def _transactions(self, period: _Period) -> OverviewTransactionsDto:
        rate_table = await self._pricing_repository.get_rate_table()
        report_currency = rate_table.anchor
        daily_by_currency = await self._transaction_repository.daily_paid_revenue_by_currency(
            period.since
        )
        daily_converted: list[tuple[date, Decimal]] = [
            (
                day,
                sum(
                    (
                        convert_for_report(amount, currency, report_currency, rate_table)
                        for currency, amount in by_currency.items()
                    ),
                    start=Decimal(0),
                ),
            )
            for day, by_currency in sorted(daily_by_currency.items())
        ]
        return OverviewTransactionsDto(
            paid_orders_count=await self._transaction_repository.count_paid_since(period.since),
            revenue_by_currency=await self._transaction_repository.sum_paid_final_price_since(
                period.since
            ),
            report_currency=report_currency,
            daily_revenue=[
                DailyAmountDto(day=day, amount=amount)
                for day, amount in period.bucketize(daily_converted, Decimal(0))
            ],
        )

    async def _runtime(self) -> list[RuntimeProcessDto]:
        now = time.time()
        return [
            RuntimeProcessDto(
                process=hb.process,
                pid=hb.pid,
                uptime_seconds=now - hb.started_at,
                rss_bytes=hb.rss_bytes,
                event_loop_delay_ms=hb.event_loop_delay_ms,
                event_loop_p99_ms=hb.event_loop_p99_ms,
            )
            for hb in await read_runtime_heartbeats(self._redis)
        ]

    async def _online(self, period: _Period) -> OverviewOnlineDto:
        days = [
            period.start_date + timedelta(days=i)
            for i in range((period.today - period.start_date).days + 1)
        ]
        peak_rows = await read_daily_online_peaks(self._redis, days)
        return OverviewOnlineDto(
            current=await read_latest_online(self._redis),
            daily_peak=[
                DailyCountDto(day=day, count=count)
                for day, count in period.bucketize(peak_rows, 0, op=max)
            ],
        )


def _host_memory() -> Optional[HostMemoryDto]:
    reading = read_host_memory()
    if reading is None:
        return None
    return HostMemoryDto(total_bytes=reading.total_bytes, used_bytes=reading.used_bytes)

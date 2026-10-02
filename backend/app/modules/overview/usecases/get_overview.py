import operator
import time
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Final, TypeVar

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
        async with self._uow:
            perms = PermissionPolicy.effective_permissions(actor)
            today_start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)
            today = today_start.date()

            if data.days == 0:
                first_registration = await self._user_stats.earliest_registration(Role.USER)
                start_date = first_registration or today
            else:
                start_date = today - timedelta(days=data.days - 1)
            # Calendar-aligned to match the frontend's fillDailySeries, which
            # builds exactly `days` UTC calendar days ending today -- a rolling
            # datetime_now() - timedelta(days=days) cutoff would include a
            # partial day `days` ago and exclude part of today, so the chart's
            # daily series wouldn't sum to the same total as the period-scoped
            # card numbers (found by the final whole-branch review).
            since = today_start - timedelta(days=(today - start_date).days)
            span_days = (today - start_date).days + 1
            granularity: Granularity = "month" if span_days > _MONTHLY_THRESHOLD_DAYS else "day"
            dense = data.days == 0

            users = None
            if Permission.USERS_VIEW in perms:
                daily = await self._user_stats.count_registrations_by_day(since, Role.USER)
                reg_series = _bucketize(daily, start_date, today, granularity, 0, dense=dense)
                users = OverviewUsersDto(
                    total=await self._user_stats.count_by_role(Role.USER),
                    new_today=await self._user_stats.count_new_since(today_start, Role.USER),
                    daily_registrations=[
                        DailyCountDto(day=day, count=count) for day, count in reg_series
                    ],
                )

            subscriptions = None
            if Permission.SUBSCRIPTIONS_VIEW in perms:
                by_status = await self._subscription_stats.count_by_status()
                active = by_status.get(SubscriptionStatus.ACTIVE, 0)
                limited = by_status.get(SubscriptionStatus.LIMITED, 0)
                expired = by_status.get(SubscriptionStatus.EXPIRED, 0)
                disabled = by_status.get(SubscriptionStatus.DISABLED, 0)
                subscriptions = OverviewSubscriptionsDto(
                    total=active + limited + expired,
                    active=active,
                    limited=limited,
                    expired=expired,
                    disabled=disabled,
                    expiring_soon=await self._subscription_stats.count_expiring_between(
                        today_start, today_start + timedelta(days=7)
                    ),
                )

            transactions = None
            if Permission.TRANSACTIONS_VIEW in perms:
                revenue_by_currency = await self._transaction_repository.sum_paid_final_price_since(
                    since
                )
                rate_table = await self._pricing_repository.get_rate_table()
                report_currency = rate_table.anchor
                daily_by_currency = (
                    await self._transaction_repository.daily_paid_revenue_by_currency(since)
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
                revenue_series = _bucketize(
                    daily_converted, start_date, today, granularity, Decimal(0), dense=dense
                )
                daily_revenue = [
                    DailyAmountDto(day=day, amount=amount) for day, amount in revenue_series
                ]
                transactions = OverviewTransactionsDto(
                    paid_orders_count=await self._transaction_repository.count_paid_since(since),
                    revenue_by_currency=revenue_by_currency,
                    report_currency=report_currency,
                    daily_revenue=daily_revenue,
                )

            now = time.time()
        runtime = [
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

        host_memory_reading = read_host_memory()
        host_memory = (
            HostMemoryDto(
                total_bytes=host_memory_reading.total_bytes,
                used_bytes=host_memory_reading.used_bytes,
            )
            if host_memory_reading is not None
            else None
        )

        online_days = [start_date + timedelta(days=i) for i in range((today - start_date).days + 1)]
        peak_rows = await read_daily_online_peaks(self._redis, online_days)
        peak_series = _bucketize(peak_rows, start_date, today, granularity, 0, dense=dense, op=max)
        online = OverviewOnlineDto(
            current=await read_latest_online(self._redis),
            daily_peak=[DailyCountDto(day=day, count=count) for day, count in peak_series],
        )

        return OverviewDto(
            days=data.days,
            granularity=granularity,
            users=users,
            subscriptions=subscriptions,
            transactions=transactions,
            runtime=runtime,
            host_memory=host_memory,
            online=online,
        )

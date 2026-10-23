from datetime import datetime, timedelta
from functools import partial

from app.core.actor import Actor
from app.core.constants import TIMEZONE, ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.enums import Role, SubscriptionStatus
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.money import round_cents
from app.core.utils.time import datetime_now
from app.modules.analytics.aggregates import report_amount
from app.modules.analytics.cache import AnalyticsCache
from app.modules.analytics.dto import (
    AnalyticsDto,
    AnalyticsPeriodInfoDto,
    AnalyticsPeriodQueryDto,
    PeriodKpiDto,
    SnapshotKpiDto,
)
from app.modules.analytics.period import CONVERSION_WINDOW_DAYS, AnalyticsPeriod, resolve_period
from app.modules.pricing import PricingRepository
from app.modules.subscriptions import SubscriptionStatsRepository
from app.modules.transactions import PaidTotalsDto, TransactionStatsRepository
from app.modules.users import UserStatsRepository


def _end_point(period: AnalyticsPeriod, now: datetime) -> datetime:
    # an unfinished period is judged as of now, not its future end
    return min(period.end, now) - timedelta(microseconds=1)


def _period_kpi(
    *,
    period: AnalyticsPeriod,
    totals: PaidTotalsDto,
    new_payers: int,
    first_paid: dict[int, datetime],
    covered: dict[datetime, set[int]],
    registrations: list[tuple[int, datetime]],
    now: datetime,
) -> PeriodKpiDto:
    # registrations shifted back by the window, so each had all of it to pay
    window = timedelta(days=CONVERSION_WINDOW_DAYS)
    cohort = {
        user_id: registered_at
        for user_id, registered_at in registrations
        if period.start - window <= registered_at < period.end - window
    }
    converted = sum(
        1
        for user_id, registered_at in cohort.items()
        if user_id in first_paid
        and (
            first_paid[user_id].astimezone(TIMEZONE).date()
            - registered_at.astimezone(TIMEZONE).date()
        ).days
        <= CONVERSION_WINDOW_DAYS
    )
    base = covered[period.start]
    churned = len(base - covered[_end_point(period, now)])
    revenue = totals.revenue
    return PeriodKpiDto(
        revenue=round_cents(revenue),
        payments=totals.payments,
        paying_users=totals.paying_users,
        arppu=(round_cents(revenue / totals.paying_users) if totals.paying_users else ZERO_AMOUNT),
        new_payers=new_payers,
        conversion_cohort=len(cohort),
        converted=converted,
        conversion_rate=converted / len(cohort) if cohort else 0.0,
        churn_base=len(base),
        churned=churned,
        churn_rate=churned / len(base) if base else 0.0,
    )


class GetAnalyticsUseCase(UseCase[AnalyticsPeriodQueryDto, AnalyticsDto]):
    required_permission = Permission.ANALYTICS_VIEW

    def __init__(
        self,
        user_stats: UserStatsRepository,
        subscription_stats: SubscriptionStatsRepository,
        transaction_stats: TransactionStatsRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        cache: AnalyticsCache,
    ) -> None:
        self._user_stats = user_stats
        self._subscription_stats = subscription_stats
        self._transaction_stats = transaction_stats
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._cache = cache

    async def _execute(self, actor: Actor, data: AnalyticsPeriodQueryDto) -> AnalyticsDto:
        return await self._cache.get_or_compute(
            "get_analytics", data, AnalyticsDto, partial(self._compute, data)
        )

    async def _compute(self, data: AnalyticsPeriodQueryDto) -> AnalyticsDto:
        async with self._uow:
            now = datetime_now()
            period = resolve_period(
                data.period_from,
                data.period_to,
                earliest=await self._user_stats.earliest_registration(Role.USER),
                now=now,
            )
            previous = period.previous
            rates = await self._pricing_repository.get_rate_table()
            stats = self._transaction_stats
            registrations = await self._user_stats.list_registrations(
                previous.start - timedelta(days=CONVERSION_WINDOW_DAYS), period.end, Role.USER
            )
            first_paid = await stats.first_paid_at(
                period.end, user_ids={user_id for user_id, _ in registrations}
            )
            covered = await stats.users_covered_at(
                {point for p in (period, previous) for point in (p.start, _end_point(p, now))},
                period.end,
            )
            kpis = {
                p: _period_kpi(
                    period=p,
                    totals=await stats.paid_totals(p.start, p.end),
                    new_payers=len(await stats.first_paid_at(p.end, since=p.start)),
                    first_paid=first_paid,
                    covered=covered,
                    registrations=registrations,
                    now=now,
                )
                for p in (period, previous)
            }
            revenue_by_currency = await stats.revenue_by_currency(period.start, period.end)

            mrr_by_currency = await self._subscription_stats.sum_active_mrr_by_currency()
            mrr = round_cents(
                sum(
                    (
                        report_amount(amount, currency, rates)
                        for currency, amount in mrr_by_currency.items()
                    ),
                    start=ZERO_AMOUNT,
                )
            )

            return AnalyticsDto(
                period=AnalyticsPeriodInfoDto(
                    start=period.start,
                    end=period.end,
                    previous_start=previous.start,
                    previous_end=previous.end,
                ),
                report_currency=rates.anchor,
                revenue_by_currency=revenue_by_currency,
                conversion_window_days=CONVERSION_WINDOW_DAYS,
                current=kpis[period],
                previous=kpis[previous],
                snapshot=SnapshotKpiDto(
                    mrr=mrr,
                    paid_subscriptions=await self._subscription_stats.count_paying(),
                    limited_subscriptions=await self._subscription_stats.count_paying(
                        status=SubscriptionStatus.LIMITED
                    ),
                    active_trials=await self._subscription_stats.count_active_trials(),
                ),
            )

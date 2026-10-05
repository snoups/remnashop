from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from app.core.actor import Actor
from app.core.constants import ONE_CENT, TIMEZONE
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, Role, SubscriptionStatus
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.analytics.aggregates import report_amount
from app.modules.analytics.coverage import coverage_by_user, is_covered
from app.modules.analytics.dto import (
    AnalyticsDto,
    AnalyticsPeriodInfoDto,
    AnalyticsPeriodQueryDto,
    PeriodKpiDto,
    SnapshotKpiDto,
)
from app.modules.analytics.period import AnalyticsPeriod, resolve_period
from app.modules.pricing import PricingRepository
from app.modules.subscriptions import SubscriptionStatsRepository
from app.modules.transactions import PaidTransactionDto, TransactionStatsRepository
from app.modules.users import UserStatsRepository

_CONVERSION_WINDOW_DAYS: Final[int] = 7


def _period_kpi(
    *,
    period: AnalyticsPeriod,
    paid: list[PaidTransactionDto],
    first_paid: dict[int, datetime],
    coverage: dict[int, list[tuple[datetime, datetime]]],
    registrations: list[tuple[int, datetime]],
    now: datetime,
) -> PeriodKpiDto:
    in_period = [row for row in paid if period.start <= row.paid_at < period.end]
    revenue = sum(
        (row.anchor_final_price for row in in_period),
        start=Decimal(0),
    )
    paying = {row.user_id for row in in_period}
    # registrations shifted back by the window, so each had all of it to pay
    window = timedelta(days=_CONVERSION_WINDOW_DAYS)
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
        <= _CONVERSION_WINDOW_DAYS
    )
    # an unfinished period is judged as of now, not its future end
    end_point = min(period.end, now) - timedelta(microseconds=1)
    base = [user_id for user_id, segments in coverage.items() if is_covered(segments, period.start)]
    churned = sum(1 for user_id in base if not is_covered(coverage[user_id], end_point))
    return PeriodKpiDto(
        revenue=revenue.quantize(ONE_CENT, rounding=ROUND_HALF_UP),
        payments=len(in_period),
        paying_users=len(paying),
        arppu=(
            (revenue / len(paying)).quantize(ONE_CENT, rounding=ROUND_HALF_UP)
            if paying
            else Decimal(0)
        ),
        new_payers=sum(1 for at in first_paid.values() if period.start <= at < period.end),
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
    ) -> None:
        self._user_stats = user_stats
        self._subscription_stats = subscription_stats
        self._transaction_stats = transaction_stats
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: AnalyticsPeriodQueryDto) -> AnalyticsDto:
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
            paid = await self._transaction_stats.list_paid(None, period.end)
            first_paid, coverage = coverage_by_user(paid)
            registrations = await self._user_stats.list_registrations(
                previous.start - timedelta(days=_CONVERSION_WINDOW_DAYS), period.end, Role.USER
            )

            revenue_by_currency: dict[Currency, Decimal] = {}
            for row in paid:
                if period.start <= row.paid_at < period.end:
                    revenue_by_currency[row.currency] = (
                        revenue_by_currency.get(row.currency, Decimal(0)) + row.final_price
                    )

            mrr_by_currency = await self._subscription_stats.sum_active_mrr_by_currency()
            mrr = sum(
                (
                    report_amount(amount, currency, rates)
                    for currency, amount in mrr_by_currency.items()
                ),
                start=Decimal(0),
            ).quantize(ONE_CENT, rounding=ROUND_HALF_UP)

            return AnalyticsDto(
                period=AnalyticsPeriodInfoDto(
                    start=period.start,
                    end=period.end,
                    previous_start=previous.start,
                    previous_end=previous.end,
                ),
                report_currency=rates.anchor,
                revenue_by_currency=revenue_by_currency,
                conversion_window_days=_CONVERSION_WINDOW_DAYS,
                current=_period_kpi(
                    period=period,
                    paid=paid,
                    first_paid=first_paid,
                    coverage=coverage,
                    registrations=registrations,
                    now=now,
                ),
                previous=_period_kpi(
                    period=previous,
                    paid=paid,
                    first_paid=first_paid,
                    coverage=coverage,
                    registrations=registrations,
                    now=now,
                ),
                snapshot=SnapshotKpiDto(
                    mrr=mrr,
                    paid_subscriptions=await self._subscription_stats.count_paying(),
                    limited_subscriptions=await self._subscription_stats.count_paying(
                        status=SubscriptionStatus.LIMITED
                    ),
                    active_trials=await self._subscription_stats.count_active_trials(),
                ),
            )

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from app.core.actor import Actor
from app.core.constants import ONE_CENT
from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType, PurchaseType, Role, TransactionStatus
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.analytics.aggregates import (
    Granularity,
    bucket_index,
    bucket_starts,
    median,
)
from app.modules.analytics.dto import (
    AnalyticsPeriodInfoDto,
    GatewayStatsDto,
    GetRevenueDto,
    RevenueBucketDto,
    RevenueDto,
    RevenueGroupDto,
    RevenueTotalsDto,
)
from app.modules.analytics.period import AnalyticsPeriod, resolve_period
from app.modules.pricing import CurrencyRateTable, PricingRepository
from app.modules.transactions import (
    PaidTransactionDto,
    PaymentAttemptDto,
    TransactionStatsRepository,
)
from app.modules.users import UserStatsRepository

_ZERO: Final[Decimal] = Decimal(0)


@dataclass
class _Bucket:
    new: Decimal = _ZERO
    renew: Decimal = _ZERO
    change: Decimal = _ZERO
    previous: Decimal = _ZERO


@dataclass
class _Gateway:
    paid: int = 0
    canceled: int = 0
    failed: int = 0
    refunded: int = 0
    revenue: Decimal = _ZERO


def _cents(value: Decimal) -> Decimal:
    return value.quantize(ONE_CENT, rounding=ROUND_HALF_UP)


def _groups(groups: dict[str, list[Decimal]]) -> list[RevenueGroupDto]:
    rows = [
        RevenueGroupDto(key=key, payments=len(amounts), revenue=_cents(sum(amounts, start=_ZERO)))
        for key, amounts in groups.items()
    ]
    return sorted(rows, key=lambda row: row.revenue, reverse=True)


def _count_attempts(
    gateways: dict[PaymentGatewayType, _Gateway],
    attempts: list[PaymentAttemptDto],
) -> tuple[int, Decimal]:
    refunds = 0
    refunded = _ZERO
    for attempt in attempts:
        stats = gateways.setdefault(attempt.gateway_type, _Gateway())
        if attempt.status is TransactionStatus.CANCELED:
            stats.canceled += 1
        elif attempt.status is TransactionStatus.FAILED:
            stats.failed += 1
        elif attempt.status is TransactionStatus.REFUNDED:
            stats.refunded += 1
            refunds += 1
            refunded += attempt.anchor_final_price
    return refunds, refunded


def _build_revenue(
    *,
    period: AnalyticsPeriod,
    granularity: Granularity,
    paid: list[PaidTransactionDto],
    attempts: list[PaymentAttemptDto],
    rates: CurrencyRateTable,
) -> RevenueDto:
    previous = period.previous
    current = [r for r in paid if period.start <= r.paid_at < period.end]
    before = [r for r in paid if previous.start <= r.paid_at < previous.end]
    amount = {id(r): r.anchor_final_price for r in paid}
    starts = bucket_starts(period, granularity)
    previous_starts = bucket_starts(previous, granularity)
    buckets = [_Bucket() for _ in starts]

    for row in current:
        index = bucket_index(starts, row.paid_at)
        if 0 <= index < len(buckets):
            bucket = buckets[index]
            if row.purchase_type is PurchaseType.NEW:
                bucket.new += amount[id(row)]
            elif row.purchase_type is PurchaseType.RENEW:
                bucket.renew += amount[id(row)]
            elif row.purchase_type is PurchaseType.CHANGE:
                bucket.change += amount[id(row)]
    for row in before:
        index = bucket_index(previous_starts, row.paid_at)
        if 0 <= index < len(buckets):
            buckets[index].previous += amount[id(row)]

    revenue = sum((amount[id(r)] for r in current), start=_ZERO)
    previous_revenue = sum((amount[id(r)] for r in before), start=_ZERO)

    by_plan: dict[str, list[Decimal]] = {}
    by_duration: dict[str, list[Decimal]] = {}
    gateways: dict[PaymentGatewayType, _Gateway] = {}
    for row in current:
        by_plan.setdefault(row.plan_name, []).append(amount[id(row)])
        by_duration.setdefault(str(row.duration_days), []).append(amount[id(row)])
        stats = gateways.setdefault(row.gateway_type, _Gateway())
        stats.paid += 1
        stats.revenue += amount[id(row)]

    refunds, refunded = _count_attempts(gateways, attempts)

    return RevenueDto(
        period=AnalyticsPeriodInfoDto(
            start=period.start,
            end=period.end,
            previous_start=previous.start,
            previous_end=previous.end,
        ),
        report_currency=rates.anchor,
        granularity=granularity,
        totals=RevenueTotalsDto(
            revenue=_cents(revenue),
            payments=len(current),
            avg_check=_cents(revenue / len(current)) if current else _ZERO,
            median_check=_cents(median([amount[id(r)] for r in current])),
            refunds=refunds,
            refunded=_cents(refunded),
            previous_revenue=_cents(previous_revenue),
            previous_payments=len(before),
        ),
        series=[
            RevenueBucketDto(
                start=start,
                new=_cents(bucket.new),
                renew=_cents(bucket.renew),
                change=_cents(bucket.change),
                previous_total=_cents(bucket.previous),
            )
            for start, bucket in zip(starts, buckets, strict=True)
        ],
        by_plan=_groups(by_plan),
        by_duration=_groups(by_duration),
        gateways=sorted(
            (
                GatewayStatsDto(
                    gateway_type=gateway_type,
                    paid=stats.paid,
                    canceled=stats.canceled,
                    failed=stats.failed,
                    refunded=stats.refunded,
                    revenue=_cents(stats.revenue),
                )
                for gateway_type, stats in gateways.items()
            ),
            key=lambda stats: stats.revenue,
            reverse=True,
        ),
    )


class GetRevenueUseCase(UseCase[GetRevenueDto, RevenueDto]):
    required_permission = Permission.ANALYTICS_REVENUE_VIEW

    def __init__(
        self,
        user_stats: UserStatsRepository,
        transaction_stats: TransactionStatsRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_stats = user_stats
        self._transaction_stats = transaction_stats
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetRevenueDto) -> RevenueDto:
        async with self._uow:
            period = resolve_period(
                data.period_from,
                data.period_to,
                earliest=await self._user_stats.earliest_registration(Role.USER),
                now=datetime_now(),
            )
            rates = await self._pricing_repository.get_rate_table()
            paid = await self._transaction_stats.list_paid(period.previous.start, period.end)
            attempts = await self._transaction_stats.list_attempts(period.start, period.end)
            return _build_revenue(
                period=period,
                granularity=data.granularity,
                paid=paid,
                attempts=attempts,
                rates=rates,
            )

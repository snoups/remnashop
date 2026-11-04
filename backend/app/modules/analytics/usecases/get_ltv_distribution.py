from decimal import ROUND_HALF_UP, Decimal
from functools import partial
from typing import Final

from app.core.actor import Actor
from app.core.constants import ONE_CENT, ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.money import round_cents
from app.modules.analytics.aggregates import median
from app.modules.analytics.cache import AnalyticsCache
from app.modules.analytics.dto import LtvBucketDto, LtvDistributionDto
from app.modules.pricing import PricingRepository
from app.modules.transactions import TransactionRepository

_QUANTILE_COUNT: Final[int] = 8
_NICE_STEPS: Final[tuple[Decimal, ...]] = tuple(
    Decimal(step) for step in ("1", "1.5", "2", "3", "5", "7")
)


def _nice_floor(value: Decimal) -> Decimal:
    magnitude = Decimal(10) ** value.adjusted()
    return max(step * magnitude for step in _NICE_STEPS if step * magnitude <= value)


def _quantile_boundaries(sorted_totals: list[Decimal], quantile_count: int) -> list[Decimal]:
    n = len(sorted_totals)
    boundaries = []
    for i in range(quantile_count):
        index = min(n - 1, (i * n) // quantile_count)
        boundaries.append(sorted_totals[index])
    return sorted(set(boundaries))


def _bucketize(sorted_totals: list[Decimal], boundaries: list[Decimal]) -> list[LtvBucketDto]:
    buckets = [
        LtvBucketDto(
            label=(
                f"{format(boundaries[i].normalize(), 'f')} - "
                f"{format(boundaries[i + 1].normalize(), 'f')}"
                if i + 1 < len(boundaries)
                else f"≥ {format(boundaries[i].normalize(), 'f')}"
            ),
            lower_bound=boundaries[i],
            upper_bound=boundaries[i + 1] if i + 1 < len(boundaries) else None,
            users=0,
        )
        for i in range(len(boundaries))
    ]
    for total in sorted_totals:
        for i in range(len(buckets) - 1, -1, -1):
            if total >= buckets[i].lower_bound:
                buckets[i].users += 1
                break
    return buckets


class GetLtvDistributionUseCase(UseCase[None, LtvDistributionDto]):
    required_permission = Permission.ANALYTICS_LTV_VIEW

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        cache: AnalyticsCache,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._cache = cache

    async def _execute(self, actor: Actor, data: None) -> LtvDistributionDto:
        return await self._cache.get_or_compute(
            "get_ltv_distribution", data, LtvDistributionDto, partial(self._compute, data)
        )

    async def _compute(self, data: None) -> LtvDistributionDto:
        async with self._uow:
            rate_table = await self._pricing_repository.get_rate_table()
            report_currency = rate_table.anchor

            totals = sorted(
                (await self._transaction_repository.sum_paid_anchor_amount_per_user()).values()
            )

            if not totals:
                return LtvDistributionDto(
                    report_currency=report_currency,
                    buckets=[],
                    payers=0,
                    mean=ZERO_AMOUNT,
                    median=ZERO_AMOUNT,
                )

            raw = _quantile_boundaries(totals, min(_QUANTILE_COUNT, len(totals)))
            boundaries = sorted({ZERO_AMOUNT, *(_nice_floor(bound) for bound in raw[1:])})
            buckets = _bucketize(totals, boundaries)
            return LtvDistributionDto(
                report_currency=report_currency,
                buckets=buckets,
                payers=len(totals),
                mean=(sum(totals, start=ZERO_AMOUNT) / len(totals)).quantize(
                    ONE_CENT, rounding=ROUND_HALF_UP
                ),
                median=round_cents(median(totals)),
            )

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from app.core.actor import Actor
from app.core.constants import ONE_CENT
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.analytics.aggregates import median
from app.modules.analytics.dto import LtvBucketDto, LtvDistributionDto
from app.modules.pricing import PricingRepository, convert_for_report
from app.modules.transactions import TransactionRepository

_QUANTILE_COUNT: Final[int] = 5
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
    ) -> None:
        self._transaction_repository = transaction_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> LtvDistributionDto:
        async with self._uow:
            rate_table = await self._pricing_repository.get_rate_table()
            report_currency = rate_table.anchor

            per_user_by_currency = (
                await self._transaction_repository.sum_paid_final_price_per_user()
            )
            totals = sorted(
                sum(
                    (
                        convert_for_report(amount, currency, report_currency, rate_table)
                        for currency, amount in by_currency.items()
                    ),
                    start=Decimal(0),
                )
                for by_currency in per_user_by_currency.values()
            )

            if not totals:
                return LtvDistributionDto(
                    report_currency=report_currency,
                    buckets=[],
                    payers=0,
                    mean=Decimal(0),
                    median=Decimal(0),
                )

            raw = _quantile_boundaries(totals, min(_QUANTILE_COUNT, len(totals)))
            boundaries = sorted({Decimal(0), *(_nice_floor(bound) for bound in raw[1:])})
            buckets = _bucketize(totals, boundaries)
            return LtvDistributionDto(
                report_currency=report_currency,
                buckets=buckets,
                payers=len(totals),
                mean=(sum(totals, start=Decimal(0)) / len(totals)).quantize(
                    ONE_CENT, rounding=ROUND_HALF_UP
                ),
                median=median(totals).quantize(ONE_CENT, rounding=ROUND_HALF_UP),
            )

from decimal import Decimal
from typing import Final

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.analytics.dto import LtvBucketDto, LtvDistributionDto
from app.modules.analytics.window import convert_amount
from app.modules.payments import PaymentOrderRepository
from app.modules.pricing import PricingRepository
from app.modules.users import UserDto

_QUANTILE_COUNT: Final[int] = 5


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
                f"{boundaries[i]:.0f} - {boundaries[i + 1]:.0f}"
                if i + 1 < len(boundaries)
                else f"≥ {boundaries[i]:.0f}"
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
        payment_order_repository: PaymentOrderRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._payment_order_repository = payment_order_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> LtvDistributionDto:
        async with self._uow:
            rate_table = await self._pricing_repository.get_rate_table()
            report_currency = rate_table.anchor

            per_user_by_currency = (
                await self._payment_order_repository.sum_paid_final_price_per_user()
            )
            totals = sorted(
                sum(
                    (
                        convert_amount(amount, currency, report_currency, rate_table)
                        for currency, amount in by_currency.items()
                    ),
                    start=Decimal(0),
                )
                for by_currency in per_user_by_currency.values()
            )

            if not totals:
                return LtvDistributionDto(report_currency=report_currency, buckets=[])

            boundaries = _quantile_boundaries(totals, min(_QUANTILE_COUNT, len(totals)))
            buckets = _bucketize(totals, boundaries)
            return LtvDistributionDto(report_currency=report_currency, buckets=buckets)

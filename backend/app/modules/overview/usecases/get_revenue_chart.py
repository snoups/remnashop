from datetime import date
from decimal import Decimal

from app.core.actor import Actor
from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.exceptions import PermissionDeniedError
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.overview.dto import DailyAmountDto, GetOverviewChartDto, RevenueChartDto
from app.modules.overview.period import resolve_period
from app.modules.pricing import PricingRepository
from app.modules.transactions import TransactionRepository
from app.modules.users import UserStatsRepository


class GetRevenueChartUseCase(UseCase[GetOverviewChartDto, RevenueChartDto]):
    # gated inside by the section's own read permission, like GetOverviewUseCase
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        user_stats: UserStatsRepository,
        transaction_repository: TransactionRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_stats = user_stats
        self._transaction_repository = transaction_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetOverviewChartDto) -> RevenueChartDto:
        if Permission.TRANSACTIONS_VIEW not in PermissionPolicy.effective_permissions(actor):
            raise PermissionDeniedError
        async with self._uow:
            period = await resolve_period(self._user_stats, data.days)
            rate_table = await self._pricing_repository.get_rate_table()
            report_currency = rate_table.anchor
            daily = await self._transaction_repository.daily_paid_anchor_revenue(period.since)
            daily_converted: list[tuple[date, Decimal]] = sorted(daily.items())
            return RevenueChartDto(
                days=data.days,
                granularity=period.granularity,
                paid_orders_count=await self._transaction_repository.count_paid_since(period.since),
                revenue_by_currency=await self._transaction_repository.sum_paid_final_price_since(
                    period.since
                ),
                report_currency=report_currency,
                daily=[
                    DailyAmountDto(day=day, amount=amount)
                    for day, amount in period.bucketize(daily_converted, ZERO_AMOUNT)
                ],
            )

from decimal import Decimal

from app.core.actor import Actor
from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.money import round_cents
from app.modules.advertising.dto import AdLinkStatsDto, GetAdLinkStatsDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.pricing import PricingRepository, convert_for_report
from app.modules.transactions import TransactionRepository


class GetAdLinkStatsUseCase(UseCase[GetAdLinkStatsDto, AdLinkStatsDto]):
    required_permission = Permission.AD_LINKS_STATS_VIEW

    def __init__(
        self,
        ad_link_repository: AdLinkRepository,
        transaction_repository: TransactionRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._ad_link_repository = ad_link_repository
        self._transaction_repository = transaction_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetAdLinkStatsDto) -> AdLinkStatsDto:
        async with self._uow:
            ad_link = await self._ad_link_repository.get_by_id(data.ad_link_id)

            attributions_count = await self._ad_link_repository.count_attributions(
                data.ad_link_id, created_from=data.created_from, created_to=data.created_to
            )
            attributions_by_channel = await self._ad_link_repository.count_attributions_by_channel(
                data.ad_link_id, created_from=data.created_from, created_to=data.created_to
            )
            user_ids = await self._ad_link_repository.list_attributed_user_ids(
                data.ad_link_id, created_from=data.created_from, created_to=data.created_to
            )

            paid_user_ids = await self._transaction_repository.list_user_ids_with_paid_order(
                user_ids
            )
            revenue_anchor = await self._transaction_repository.sum_paid_anchor_amount_by_user_ids(
                user_ids
            )

            rate_table = await self._pricing_repository.get_rate_table()
            report_currency = rate_table.anchor

            revenue = convert_for_report(
                revenue_anchor, rate_table.anchor, report_currency, rate_table
            )
            fixed_cost = convert_for_report(
                ad_link.cost, ad_link.cost_currency, report_currency, rate_table
            )
            revenue_share = ad_link.revenue_share(revenue)
            cost = fixed_cost + revenue_share

            cpa = round_cents(cost / len(paid_user_ids)) if paid_user_ids else None
            roi = (revenue - cost) / cost if cost > 0 else None
            conversion_rate = (
                Decimal(len(paid_user_ids)) / attributions_count
                if attributions_count > 0
                else ZERO_AMOUNT
            )

            daily = await self._ad_link_repository.daily_attribution_counts(
                data.ad_link_id, created_from=data.created_from, created_to=data.created_to
            )

            return AdLinkStatsDto(
                attributions_count=attributions_count,
                attributions_by_channel=attributions_by_channel,
                paid_count=len(paid_user_ids),
                conversion_rate=conversion_rate,
                revenue=revenue,
                cost=cost,
                fixed_cost=fixed_cost,
                revenue_share_percent=ad_link.revenue_share_percent,
                revenue_share=revenue_share,
                report_currency=report_currency,
                cpa=cpa,
                roi=roi,
                daily_registrations=daily,
            )

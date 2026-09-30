from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from app.core.constants import ONE_CENT
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import AdLinkStatsDto, GetAdLinkStatsDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.payments import PaymentOrderRepository
from app.modules.pricing import PricingRepository, convert_for_report
from app.modules.users import UserDto

_ZERO: Final[Decimal] = Decimal(0)


class GetAdLinkStatsUseCase(UseCase[GetAdLinkStatsDto, AdLinkStatsDto]):
    required_permission = Permission.AD_LINKS_STATS_VIEW

    def __init__(
        self,
        ad_link_repository: AdLinkRepository,
        payment_order_repository: PaymentOrderRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._ad_link_repository = ad_link_repository
        self._payment_order_repository = payment_order_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: GetAdLinkStatsDto) -> AdLinkStatsDto:
        async with self._uow:
            ad_link = await self._ad_link_repository.get_by_id(data.ad_link_id)

            since = data.created_from
            attributions_count = await self._ad_link_repository.count_attributions(
                data.ad_link_id, created_from=since
            )
            attributions_by_channel = await self._ad_link_repository.count_attributions_by_channel(
                data.ad_link_id, created_from=since
            )
            user_ids = await self._ad_link_repository.list_attributed_user_ids(
                data.ad_link_id, created_from=since
            )

            paid_user_ids = await self._payment_order_repository.list_user_ids_with_paid_order(
                user_ids
            )
            revenue_by_currency = (
                await self._payment_order_repository.sum_paid_final_price_by_user_ids(user_ids)
            )

            rate_table = await self._pricing_repository.get_rate_table()
            report_currency = data.report_currency or rate_table.anchor

            revenue = sum(
                (
                    convert_for_report(amount, currency, report_currency, rate_table)
                    for currency, amount in revenue_by_currency.items()
                ),
                start=_ZERO,
            )
            cost = convert_for_report(
                ad_link.cost, ad_link.cost_currency, report_currency, rate_table
            )

            cpa = (
                (cost / len(paid_user_ids)).quantize(ONE_CENT, rounding=ROUND_HALF_UP)
                if paid_user_ids
                else None
            )
            roi = (revenue - cost) / cost if cost > 0 else None
            conversion_rate = (
                Decimal(len(paid_user_ids)) / attributions_count
                if attributions_count > 0
                else _ZERO
            )

            daily = await self._ad_link_repository.daily_attribution_counts(
                data.ad_link_id, created_from=since
            )

            return AdLinkStatsDto(
                attributions_count=attributions_count,
                attributions_by_channel=attributions_by_channel,
                paid_count=len(paid_user_ids),
                conversion_rate=conversion_rate,
                revenue=revenue,
                revenue_by_currency=revenue_by_currency,
                cost=cost,
                report_currency=report_currency,
                cpa=cpa,
                roi=roi,
                daily_registrations=daily,
            )

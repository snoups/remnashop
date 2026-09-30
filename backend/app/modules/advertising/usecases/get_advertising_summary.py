from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from app.core.constants import ONE_CENT
from app.core.db.uow import UnitOfWork
from app.core.enums import AdLinkChannel
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import (
    AdLinkMetricsDto,
    AdvertisingSummaryDto,
    GetAdvertisingSummaryDto,
)
from app.modules.advertising.repository import AdLinkRepository
from app.modules.payments import PaymentOrderRepository
from app.modules.pricing import PricingRepository, convert_for_report
from app.modules.users import UserDto

_ZERO: Final[Decimal] = Decimal(0)


class GetAdvertisingSummaryUseCase(UseCase[GetAdvertisingSummaryDto, AdvertisingSummaryDto]):
    required_permission = Permission.AD_LINKS_SUMMARY_VIEW

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

    async def _execute(
        self, actor: UserDto, data: GetAdvertisingSummaryDto
    ) -> AdvertisingSummaryDto:
        async with self._uow:
            ad_links = await self._ad_link_repository.list_all(is_active=data.is_active)
            attributions = await self._ad_link_repository.list_attributions(
                [link.id for link in ad_links],
                created_from=data.created_from,
                created_to=data.created_to,
            )
            # aggregates every payer, not just attributed ones; filter by
            # user_ids in SQL if the paid-user count gets large.
            paid_by_user = await self._payment_order_repository.sum_paid_final_price_per_user(
                created_before=data.created_to
            )
            rate_table = await self._pricing_repository.get_rate_table()

        report_currency = data.report_currency or rate_table.anchor
        revenue_by_user = {
            user_id: sum(
                (
                    convert_for_report(amount, currency, report_currency, rate_table)
                    for currency, amount in amounts.items()
                ),
                start=_ZERO,
            )
            for user_id, amounts in paid_by_user.items()
        }

        users_by_link: defaultdict[int, list[int]] = defaultdict(list)
        by_channel: defaultdict[AdLinkChannel, int] = defaultdict(int)
        for ad_link_id, user_id, channel in attributions:
            users_by_link[ad_link_id].append(user_id)
            by_channel[channel] += 1

        links: list[AdLinkMetricsDto] = []
        for link in ad_links:
            user_ids = users_by_link[link.id]
            paid = [user_id for user_id in user_ids if user_id in revenue_by_user]
            revenue = sum((revenue_by_user[user_id] for user_id in paid), start=_ZERO)
            cost = convert_for_report(link.cost, link.cost_currency, report_currency, rate_table)
            links.append(
                AdLinkMetricsDto(
                    ad_link_id=link.id,
                    attributions_count=len(user_ids),
                    paid_count=len(paid),
                    revenue=revenue,
                    cost=cost,
                    roi=(revenue - cost) / cost if cost > 0 else None,
                )
            )

        attributions_count = len(attributions)
        paid_count = sum(link.paid_count for link in links)
        revenue = sum((link.revenue for link in links), start=_ZERO)
        cost = sum((link.cost for link in links), start=_ZERO)
        return AdvertisingSummaryDto(
            report_currency=report_currency,
            attributions_count=attributions_count,
            attributions_by_channel=dict(by_channel),
            paid_count=paid_count,
            conversion_rate=(
                Decimal(paid_count) / attributions_count if attributions_count > 0 else _ZERO
            ),
            revenue=revenue,
            cost=cost,
            cpa=(
                (cost / paid_count).quantize(ONE_CENT, rounding=ROUND_HALF_UP)
                if paid_count > 0
                else None
            ),
            roi=(revenue - cost) / cost if cost > 0 else None,
            links=links,
        )

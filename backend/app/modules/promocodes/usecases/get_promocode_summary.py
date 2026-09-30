from decimal import Decimal

from app.core.db.uow import UnitOfWork
from app.core.enums import PromocodeRewardType
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.payments import PaymentOrderRepository
from app.modules.pricing import PricingRepository, convert_for_report
from app.modules.promocodes.dto import PromocodeSummaryDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users import UserDto


class GetPromocodeSummaryUseCase(UseCase[None, PromocodeSummaryDto]):
    required_permission = Permission.PROMOCODES_SUMMARY_VIEW

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        payment_order_repository: PaymentOrderRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._payment_order_repository = payment_order_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> PromocodeSummaryDto:
        async with self._uow:
            promocodes = await self._promocode_repository.list_all()
            by_promocode = await self._promocode_repository.count_activations_by_promocode()
            activations, users = await self._promocode_repository.count_activations()
            # the reward is fixed at creation, so summing it over activations is exact
            totals = await self._promocode_repository.reward_totals_by_type()
            (
                discounted_orders,
                discounts,
            ) = await self._payment_order_repository.sum_paid_promocode_discounts()
            rate_table = await self._pricing_repository.get_rate_table()

        now = datetime_now()
        report_currency = rate_table.anchor
        duration = totals.get(PromocodeRewardType.DURATION)
        subscription = totals.get(PromocodeRewardType.SUBSCRIPTION)

        return PromocodeSummaryDto(
            total_count=len(promocodes),
            active_count=sum(
                1
                for promo in promocodes
                if promo.is_active and (promo.expires_at is None or promo.expires_at > now)
            ),
            activations_count=activations,
            activated_users_count=users,
            activations_by_promocode=by_promocode,
            granted_days=(duration.reward_sum if duration else 0)
            + (subscription.duration_days_sum if subscription else 0),
            granted_subscriptions_count=subscription.count if subscription else 0,
            report_currency=report_currency,
            discount_amount=sum(
                (
                    convert_for_report(amount, currency, report_currency, rate_table)
                    for currency, amount in discounts.items()
                ),
                start=Decimal(0),
            ),
            discounted_orders_count=discounted_orders,
        )

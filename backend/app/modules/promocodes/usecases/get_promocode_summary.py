from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PromocodeRewardType
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.pricing import PricingRepository
from app.modules.promocodes.dto import PromocodeSummaryDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.transactions import TransactionRepository


class GetPromocodeSummaryUseCase(UseCase[None, PromocodeSummaryDto]):
    required_permission = Permission.PROMOCODES_SUMMARY_VIEW

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        transaction_repository: TransactionRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._transaction_repository = transaction_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> PromocodeSummaryDto:
        now = datetime_now()
        async with self._uow:
            total_count, active_count = await self._promocode_repository.count_total_and_active(now)
            activations, users = await self._promocode_repository.count_activations()
            # the reward is fixed at creation, so summing it over activations is exact
            totals = await self._promocode_repository.reward_totals_by_type()
            (
                discounted_orders,
                discount_amount,
            ) = await self._transaction_repository.sum_paid_promocode_discounts()
            rate_table = await self._pricing_repository.get_rate_table()

        report_currency = rate_table.anchor
        duration = totals.get(PromocodeRewardType.DURATION)
        subscription = totals.get(PromocodeRewardType.SUBSCRIPTION)

        return PromocodeSummaryDto(
            total_count=total_count,
            active_count=active_count,
            activations_count=activations,
            activated_users_count=users,
            granted_days=(duration.reward_sum if duration else 0)
            + (subscription.duration_days_sum if subscription else 0),
            granted_subscriptions_count=subscription.count if subscription else 0,
            report_currency=report_currency,
            discount_amount=discount_amount,
            discounted_orders_count=discounted_orders,
        )

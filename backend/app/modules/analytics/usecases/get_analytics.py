from datetime import timedelta
from decimal import Decimal
from typing import Final

from app.core.db.uow import UnitOfWork
from app.core.enums import Role, SubscriptionStatus
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.analytics.dto import (
    AnalyticsDto,
    AnalyticsKpiDto,
    ChurnSnapshotDto,
    GetAnalyticsDto,
)
from app.modules.analytics.window import convert_amount, resolve_since
from app.modules.payments import PaymentOrderRepository
from app.modules.pricing import PricingRepository
from app.modules.subscriptions import SubscriptionRepository
from app.modules.users import UserDto, UserRepository

_ALL_TIME_CHURN_WINDOW_DAYS: Final[int] = 30


class GetAnalyticsUseCase(UseCase[GetAnalyticsDto, AnalyticsDto]):
    required_permission = Permission.ANALYTICS_VIEW

    def __init__(
        self,
        user_repository: UserRepository,
        subscription_repository: SubscriptionRepository,
        payment_order_repository: PaymentOrderRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository
        self._payment_order_repository = payment_order_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: GetAnalyticsDto) -> AnalyticsDto:
        since = await resolve_since(self._user_repository, data.days)
        async with self._uow:
            today_start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)

            rate_table = await self._pricing_repository.get_rate_table()
            report_currency = rate_table.anchor

            active_subscriptions = (await self._subscription_repository.count_by_status()).get(
                SubscriptionStatus.ACTIVE, 0
            )

            total_revenue_by_currency = (
                await self._payment_order_repository.sum_paid_final_price_since(since)
            )
            total_revenue = sum(
                (
                    convert_amount(amount, currency, report_currency, rate_table)
                    for currency, amount in total_revenue_by_currency.items()
                ),
                start=Decimal(0),
            )

            mrr_by_currency = await self._subscription_repository.sum_active_mrr_by_currency()
            mrr = sum(
                (
                    convert_amount(amount, currency, report_currency, rate_table)
                    for currency, amount in mrr_by_currency.items()
                ),
                start=Decimal(0),
            )

            registered_ids = await self._user_repository.list_ids_registered_since(since, Role.USER)
            paid_ids = await self._payment_order_repository.list_user_ids_with_paid_order(
                registered_ids
            )

            kpi = AnalyticsKpiDto(
                total_revenue_by_currency=total_revenue_by_currency,
                report_currency=report_currency,
                mrr=mrr,
                arpu=(total_revenue / active_subscriptions) if active_subscriptions else Decimal(0),
                active_subscriptions=active_subscriptions,
                paid_orders_count=await self._payment_order_repository.count_paid_since(since),
                registered_in_period=len(registered_ids),
                paid_in_period=len(paid_ids),
                conversion_rate=(len(paid_ids) / len(registered_ids)) if registered_ids else 0.0,
            )

            churn_window_days = _ALL_TIME_CHURN_WINDOW_DAYS if data.days == 0 else data.days
            churn_since = (
                today_start - timedelta(days=_ALL_TIME_CHURN_WINDOW_DAYS - 1)
                if data.days == 0
                else since
            )
            prev_active, still_active = await self._subscription_repository.count_churn_window(
                churn_since
            )
            churn = ChurnSnapshotDto(
                window_days=churn_window_days,
                prev_active=prev_active,
                still_active=still_active,
                churned=prev_active - still_active,
                churn_rate=((prev_active - still_active) / prev_active) if prev_active else 0.0,
                retention_rate=(still_active / prev_active) if prev_active else 1.0,
            )

            return AnalyticsDto(days=data.days, kpi=kpi, churn=churn)

from datetime import timedelta
from decimal import Decimal

from app.core.enums import Currency, Role
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.overview.dto import (
    DailyAmountDto,
    DailyCountDto,
    GetOverviewDto,
    OverviewDto,
    OverviewPaymentsDto,
    OverviewSubscriptionsDto,
    OverviewUsersDto,
)
from app.modules.payments import PaymentOrderRepository
from app.modules.pricing import CurrencyRateTable, PricingRepository
from app.modules.subscriptions import SubscriptionRepository
from app.modules.users import UserDto, UserRepository


def _convert(
    amount: Decimal, from_currency: Currency, to_currency: Currency, rates: CurrencyRateTable
) -> Decimal:
    # Display-only reporting conversion, same shape as advertising's own
    # _convert() -- not app.modules.pricing.resolve_price, no rounding/charm-
    # ending rules apply to a revenue chart.
    if from_currency == to_currency:
        return amount
    anchor_amount = amount / rates.for_currency(from_currency).rate
    return anchor_amount * rates.for_currency(to_currency).rate


class GetOverviewUseCase(UseCase[GetOverviewDto, OverviewDto]):
    # Every admin may call this -- gating happens per-section below, not at
    # the router/permission-check level, since no single Permission covers
    # "can see the overview page".
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        user_repository: UserRepository,
        subscription_repository: SubscriptionRepository,
        payment_order_repository: PaymentOrderRepository,
        pricing_repository: PricingRepository,
    ) -> None:
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository
        self._payment_order_repository = payment_order_repository
        self._pricing_repository = pricing_repository

    async def _execute(self, actor: UserDto, data: GetOverviewDto) -> OverviewDto:
        perms = PermissionPolicy.effective_permissions(actor)
        today_start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Calendar-aligned to match the frontend's fillDailySeries, which
        # builds exactly `days` UTC calendar days ending today -- a rolling
        # datetime_now() - timedelta(days=days) cutoff would include a
        # partial day `days` ago and exclude part of today, so the chart's
        # daily series wouldn't sum to the same total as the period-scoped
        # card numbers (found by the final whole-branch review).
        since = today_start - timedelta(days=data.days - 1)

        users = None
        if Permission.USERS_VIEW in perms:
            daily = await self._user_repository.count_registrations_by_day(since, Role.USER)
            users = OverviewUsersDto(
                total=await self._user_repository.count_by_role(Role.USER),
                new_today=await self._user_repository.count_new_since(today_start, Role.USER),
                daily_registrations=[DailyCountDto(day=day, count=count) for day, count in daily],
            )

        subscriptions = None
        if Permission.SUBSCRIPTIONS_VIEW in perms:
            subscriptions = OverviewSubscriptionsDto(
                active=await self._subscription_repository.count_active(),
            )

        payments = None
        if Permission.PAYMENTS_VIEW in perms:
            revenue_by_currency = await self._payment_order_repository.sum_paid_final_price_since(
                since
            )
            rate_table = await self._pricing_repository.get_rate_table()
            report_currency = rate_table.anchor
            daily_by_currency = await self._payment_order_repository.daily_paid_revenue_by_currency(
                since
            )
            daily_revenue = [
                DailyAmountDto(
                    day=day,
                    amount=sum(
                        (
                            _convert(amount, currency, report_currency, rate_table)
                            for currency, amount in by_currency.items()
                        ),
                        start=Decimal(0),
                    ),
                )
                for day, by_currency in sorted(daily_by_currency.items())
            ]
            payments = OverviewPaymentsDto(
                paid_orders_count=await self._payment_order_repository.count_paid_since(since),
                revenue_by_currency=revenue_by_currency,
                report_currency=report_currency,
                daily_revenue=daily_revenue,
            )

        return OverviewDto(
            days=data.days, users=users, subscriptions=subscriptions, payments=payments
        )

from datetime import UTC, datetime
from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.money import round_cents
from app.core.utils.time import datetime_now
from app.modules.overview.dto import RecapDto
from app.modules.overview.usecases.get_nodes_overview import GetNodesOverviewUseCase
from app.modules.pricing import PricingRepository
from app.modules.subscriptions import SubscriptionStatsRepository
from app.modules.transactions import TransactionStatsRepository
from app.modules.users import UserStatsRepository

# before any shop's first payment: "all time" for paid_totals
_ALL_TIME_START: Final[datetime] = datetime(1970, 1, 1, tzinfo=UTC)


class GetRecapUseCase(UseCase[None, RecapDto]):
    required_permission = Permission.OVERVIEW_RECAP_VIEW

    def __init__(
        self,
        user_stats: UserStatsRepository,
        subscription_stats: SubscriptionStatsRepository,
        transaction_stats: TransactionStatsRepository,
        pricing_repository: PricingRepository,
        get_nodes_overview_use_case: GetNodesOverviewUseCase,
        uow: UnitOfWork,
    ) -> None:
        self._user_stats = user_stats
        self._subscription_stats = subscription_stats
        self._transaction_stats = transaction_stats
        self._pricing_repository = pricing_repository
        self._get_nodes_overview_use_case = get_nodes_overview_use_case
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> RecapDto:
        now = datetime_now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        async with self._uow:
            report_currency = (await self._pricing_repository.get_rate_table()).anchor
            users = await self._user_stats.count_total_and_new(Role.USER, month_start)
            since = await self._user_stats.earliest_registration(Role.USER)
            subscriptions = await self._subscription_stats.overview_counts(now, now)
            all_time = await self._transaction_stats.paid_totals(_ALL_TIME_START, now)
            month = await self._transaction_stats.paid_totals(month_start, now)
            new_payers = await self._transaction_stats.first_paid_at(now, since=month_start)

        # the panel is outside the transaction: a slow or down panel only empties its two numbers
        nodes = await self._get_nodes_overview_use_case(actor)
        live_nodes = [node for node in nodes.nodes if not node.is_disabled]
        return RecapDto(
            report_currency=report_currency,
            revenue_total=round_cents(all_time.revenue),
            customers=users.total,
            payers=all_time.paying_users,
            active_subscriptions=subscriptions.paid_active,
            transactions=all_time.payments,
            month_revenue=round_cents(month.revenue),
            new_customers=users.new,
            new_payers=len(new_payers),
            nodes=len(live_nodes) if nodes.available else None,
            countries=len({node.country_code for node in live_nodes}) if nodes.available else None,
            since=since or now.date(),
        )

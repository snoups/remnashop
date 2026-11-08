from functools import partial

from app.core.actor import Actor
from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.money import round_cents
from app.core.utils.time import datetime_now
from app.modules.analytics.cache import AnalyticsCache
from app.modules.analytics.dto import (
    ExpiringCustomerDto,
    ExpiringCustomerPageDto,
    ListExpiringCustomersDto,
)
from app.modules.analytics.expiring import expiring_window
from app.modules.subscriptions import LiveSubscriptionDto, SubscriptionStatsRepository
from app.modules.transactions import TransactionStatsRepository
from app.modules.users import UserRepository


class ListExpiringCustomersUseCase(UseCase[ListExpiringCustomersDto, ExpiringCustomerPageDto]):
    required_permission = Permission.ANALYTICS_EXPIRING_VIEW

    def __init__(
        self,
        subscription_stats: SubscriptionStatsRepository,
        transaction_stats: TransactionStatsRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
        cache: AnalyticsCache,
    ) -> None:
        self._subscription_stats = subscription_stats
        self._transaction_stats = transaction_stats
        self._user_repository = user_repository
        self._uow = uow
        self._cache = cache

    async def _execute(
        self, actor: Actor, data: ListExpiringCustomersDto
    ) -> ExpiringCustomerPageDto:
        return await self._cache.get_or_compute(
            "list_expiring_customers",
            data,
            ExpiringCustomerPageDto,
            partial(self._compute, data),
        )

    async def _compute(self, data: ListExpiringCustomersDto) -> ExpiringCustomerPageDto:
        async with self._uow:
            now = datetime_now()
            live = await self._subscription_stats.list_live()
            expiring = [row for row in expiring_window(live, now) if not row.is_trial]
            summaries = await self._transaction_stats.payer_summaries(
                now, user_ids={row.user_id for row in expiring}
            )
            spent = {s.user_id: s.spent for s in summaries}
            renewals = {s.user_id: s.renewals for s in summaries}
            nearest: dict[int, LiveSubscriptionDto] = {}
            plan_names: dict[int, list[str]] = {}
            for row in sorted(expiring, key=lambda r: r.expire_at):
                nearest.setdefault(row.user_id, row)
                plan_names.setdefault(row.user_id, []).append(row.plan_name)
            # a customer ranking: staff subscriptions are not shown to anyone
            staff = await self._user_repository.list_staff_ids()
            ranked = sorted(
                (row for row in nearest.values() if row.user_id not in staff),
                key=lambda r: spent.get(r.user_id, ZERO_AMOUNT),
                reverse=True,
            )
            start = (data.page - 1) * data.page_size
            page = ranked[start : start + data.page_size]
            users = {
                u.id: u for u in await self._user_repository.list_by_ids([r.user_id for r in page])
            }
        return ExpiringCustomerPageDto(
            items=[
                ExpiringCustomerDto(
                    user_id=row.user_id,
                    name=users[row.user_id].name if row.user_id in users else "",
                    username=users[row.user_id].username if row.user_id in users else None,
                    plan_names=plan_names[row.user_id],
                    expire_at=row.expire_at,
                    spent=round_cents(spent.get(row.user_id, ZERO_AMOUNT)),
                    renewals=renewals.get(row.user_id, 0),
                )
                for row in page
            ],
            total=len(ranked),
        )

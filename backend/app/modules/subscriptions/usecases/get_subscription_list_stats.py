from datetime import timedelta
from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import SubscriptionListStatsDto
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository

EXPIRING_WITHIN: Final[timedelta] = timedelta(days=7)
EXPIRING_URGENT: Final[timedelta] = timedelta(hours=24)


class GetSubscriptionListStatsUseCase(UseCase[None, SubscriptionListStatsDto]):
    required_permission = Permission.SUBSCRIPTIONS_STATS_VIEW

    def __init__(self, subscription_stats: SubscriptionStatsRepository, uow: UnitOfWork) -> None:
        self._subscription_stats = subscription_stats
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> SubscriptionListStatsDto:
        now = datetime_now()
        stats = self._subscription_stats
        async with self._uow:
            counts = await stats.overview_counts(now, now + EXPIRING_WITHIN)
            expiring, expiring_urgent = await stats.count_expiring_paid(
                now, now + EXPIRING_WITHIN, now + EXPIRING_URGENT
            )
            return SubscriptionListStatsDto(
                paid_active=counts.paid_active,
                active_trials=counts.active_trials,
                expiring=expiring,
                expiring_urgent=expiring_urgent,
                limited=counts.limited,
                disabled=counts.disabled,
                paying=await stats.count_paying(),
                paying_never_connected=await stats.count_paying_never_connected(),
            )

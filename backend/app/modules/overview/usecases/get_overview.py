import time
from datetime import datetime, timedelta
from typing import Optional

from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role, SubscriptionStatus
from app.core.runtime_heartbeat import read_host_memory, read_runtime_heartbeats
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.overview.dto import (
    HostMemoryDto,
    OverviewDto,
    OverviewSubscriptionsDto,
    OverviewUsersDto,
    RuntimeProcessDto,
)
from app.modules.subscriptions import SubscriptionStatsRepository
from app.modules.users import UserStatsRepository


class GetOverviewUseCase(UseCase[None, OverviewDto]):
    # Every admin may call this -- gating happens per-section below, not at
    # the router/permission-check level, since no single Permission covers
    # "can see the overview page".
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        user_stats: UserStatsRepository,
        subscription_stats: SubscriptionStatsRepository,
        redis: Redis,
        uow: UnitOfWork,
    ) -> None:
        self._user_stats = user_stats
        self._subscription_stats = subscription_stats
        self._redis = redis
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> OverviewDto:
        perms = PermissionPolicy.effective_permissions(actor)
        today_start = datetime_now().replace(hour=0, minute=0, second=0, microsecond=0)
        async with self._uow:
            users = await self._users(today_start) if Permission.USERS_VIEW in perms else None
            subscriptions = (
                await self._subscriptions(today_start)
                if Permission.SUBSCRIPTIONS_VIEW in perms
                else None
            )

        return OverviewDto(
            users=users,
            subscriptions=subscriptions,
            runtime=await self._runtime(),
            host_memory=_host_memory(),
        )

    async def _users(self, today_start: datetime) -> OverviewUsersDto:
        return OverviewUsersDto(
            total=await self._user_stats.count_by_role(Role.USER),
            new_today=await self._user_stats.count_new_since(today_start, Role.USER),
        )

    async def _subscriptions(self, today_start: datetime) -> OverviewSubscriptionsDto:
        by_status = await self._subscription_stats.count_by_status()
        active = by_status.get(SubscriptionStatus.ACTIVE, 0)
        limited = by_status.get(SubscriptionStatus.LIMITED, 0)
        expired = by_status.get(SubscriptionStatus.EXPIRED, 0)
        return OverviewSubscriptionsDto(
            total=active + limited + expired,
            active=active,
            limited=limited,
            expired=expired,
            disabled=by_status.get(SubscriptionStatus.DISABLED, 0),
            expiring_soon=await self._subscription_stats.count_expiring_between(
                today_start, today_start + timedelta(days=7)
            ),
        )

    async def _runtime(self) -> list[RuntimeProcessDto]:
        now = time.time()
        return [
            RuntimeProcessDto(
                process=hb.process,
                pid=hb.pid,
                uptime_seconds=now - hb.started_at,
                rss_bytes=hb.rss_bytes,
                event_loop_delay_ms=hb.event_loop_delay_ms,
                event_loop_p99_ms=hb.event_loop_p99_ms,
            )
            for hb in await read_runtime_heartbeats(self._redis)
        ]


def _host_memory() -> Optional[HostMemoryDto]:
    reading = read_host_memory()
    if reading is None:
        return None
    return HostMemoryDto(total_bytes=reading.total_bytes, used_bytes=reading.used_bytes)

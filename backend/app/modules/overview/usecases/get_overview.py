import os
import time
from datetime import datetime, timedelta
from typing import Final, Optional

from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.host_metrics import read_host_cpu_percent, read_host_disk, read_host_load
from app.core.runtime_heartbeat import (
    RUNTIME_PROCESSES,
    read_host_memory,
    read_runtime_heartbeats,
)
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.core.utils.money import round_cents
from app.core.utils.time import datetime_now
from app.modules.overview.dto import (
    HostMemoryDto,
    HostStatsDto,
    OverviewDto,
    OverviewSubscriptionsDto,
    OverviewUsersDto,
    RecentPaymentDto,
    RevenueTodayDto,
    RuntimeProcessDto,
)
from app.modules.pricing import PricingRepository
from app.modules.subscriptions import SubscriptionStatsRepository
from app.modules.transactions import TransactionStatsRepository
from app.modules.users import UserRepository, UserStatsRepository

_RECENT_PAYMENTS: Final[int] = 8


class GetOverviewUseCase(UseCase[None, OverviewDto]):
    # open to every admin: each section below checks its own permission, since
    # no single Permission covers the overview page
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        user_stats: UserStatsRepository,
        subscription_stats: SubscriptionStatsRepository,
        transaction_stats: TransactionStatsRepository,
        user_repository: UserRepository,
        pricing_repository: PricingRepository,
        redis: Redis,
        uow: UnitOfWork,
    ) -> None:
        self._user_stats = user_stats
        self._subscription_stats = subscription_stats
        self._transaction_stats = transaction_stats
        self._user_repository = user_repository
        self._pricing_repository = pricing_repository
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
            revenue_today = None
            recent_payments = None
            if Permission.TRANSACTIONS_VIEW in perms:
                revenue_today = await self._revenue_today(today_start)
                recent_payments = await self._recent_payments(actor)

        return OverviewDto(
            users=users,
            subscriptions=subscriptions,
            runtime=await self._runtime(),
            host_memory=_host_memory(),
            host=await self._host_stats(),
            revenue_today=revenue_today,
            recent_payments=recent_payments,
        )

    async def _users(self, today_start: datetime) -> OverviewUsersDto:
        counts = await self._user_stats.count_total_and_new(Role.USER, today_start)
        return OverviewUsersDto(total=counts.total, new_today=counts.new)

    async def _subscriptions(self, today_start: datetime) -> OverviewSubscriptionsDto:
        counts = await self._subscription_stats.overview_counts(
            today_start, today_start + timedelta(days=7)
        )
        return OverviewSubscriptionsDto(
            total=counts.active + counts.limited + counts.expired,
            active=counts.active,
            limited=counts.limited,
            expired=counts.expired,
            disabled=counts.disabled,
            expiring_soon=counts.expiring,
            paid_active=counts.paid_active,
            trials=counts.active_trials,
        )

    async def _revenue_today(self, today_start: datetime) -> RevenueTodayDto:
        now = datetime_now()
        rates = await self._pricing_repository.get_rate_table()
        paid = await self._transaction_stats.list_paid(today_start - timedelta(days=1), now)

        today = sum(
            (r.anchor_final_price for r in paid if r.paid_at >= today_start), start=ZERO_AMOUNT
        )
        same_time_cutoff = now - timedelta(days=1)
        yesterday = sum(
            (r.anchor_final_price for r in paid if r.paid_at < same_time_cutoff),
            start=ZERO_AMOUNT,
        )
        return RevenueTodayDto(
            report_currency=rates.anchor,
            today=round_cents(today),
            yesterday_same_time=round_cents(yesterday),
            change=float(today / yesterday - 1) if yesterday else None,
        )

    async def _recent_payments(self, actor: Actor) -> list[RecentPaymentDto]:
        # a staff payer the caller may not see is left out, as in the order list
        sees_staff = PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE)
        rows = await self._transaction_stats.list_recent_paid(
            _RECENT_PAYMENTS, hide_staff_from=None if sees_staff else actor.id
        )
        users = {
            u.id: u for u in await self._user_repository.list_by_ids([r.user_id for r in rows])
        }
        return [
            RecentPaymentDto(
                transaction_id=row.transaction_id,
                user_id=row.user_id,
                name=payer.name if (payer := users.get(row.user_id)) else "",
                plan_name=row.plan_name,
                duration_days=row.duration_days,
                gateway_type=row.gateway_type,
                purchase_type=row.purchase_type,
                amount=row.final_price,
                currency=row.currency,
                paid_at=row.paid_at,
            )
            for row in rows
        ]

    async def _runtime(self) -> list[RuntimeProcessDto]:
        now = time.time()
        heartbeats = await read_runtime_heartbeats(self._redis)
        processes: list[RuntimeProcessDto] = []
        for process in RUNTIME_PROCESSES:
            alive = [hb for hb in heartbeats if hb.process == process]
            processes += [
                RuntimeProcessDto(
                    process=hb.process,
                    instance=hb.instance,
                    pid=hb.pid,
                    uptime_seconds=now - hb.started_at,
                    rss_bytes=hb.rss_bytes,
                    event_loop_delay_ms=hb.event_loop_delay_ms,
                    event_loop_p99_ms=hb.event_loop_p99_ms,
                )
                for hb in alive
            ] or [RuntimeProcessDto(process=process)]
        return processes

    async def _host_stats(self) -> Optional[HostStatsDto]:
        cpu_percent = await read_host_cpu_percent()
        load = read_host_load()
        disk = read_host_disk("/")

        if cpu_percent is None and load is None and disk is None:
            return None

        cpu_count = load.cpu_count if load is not None else os.cpu_count() or 1

        return HostStatsDto(
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            load_1=load.load_1 if load is not None else None,
            load_5=load.load_5 if load is not None else None,
            load_15=load.load_15 if load is not None else None,
            disk_total_bytes=disk.total_bytes if disk is not None else None,
            disk_used_bytes=disk.used_bytes if disk is not None else None,
        )


def _host_memory() -> Optional[HostMemoryDto]:
    reading = read_host_memory()
    if reading is None:
        return None
    return HostMemoryDto(total_bytes=reading.total_bytes, used_bytes=reading.used_bytes)

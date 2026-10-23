from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from functools import partial
from typing import Final

from app.core.actor import Actor
from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.enums import PromocodeRewardType, PromocodeStatus, Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.money import round_cents
from app.core.utils.time import datetime_now
from app.modules.analytics.cache import AnalyticsCache
from app.modules.analytics.dto import (
    AnalyticsPeriodInfoDto,
    AnalyticsPeriodQueryDto,
    PromocodeRowDto,
    PromocodeStatsDto,
    RewardTypeCountDto,
)
from app.modules.analytics.period import resolve_period
from app.modules.pricing import PricingRepository
from app.modules.promocodes import PromocodeDto, PromocodeRepository
from app.modules.transactions import TransactionStatsRepository
from app.modules.users import UserStatsRepository

_FREE_REWARD_TYPES: Final[frozenset[PromocodeRewardType]] = frozenset(
    {
        PromocodeRewardType.DURATION,
        PromocodeRewardType.TRAFFIC,
        PromocodeRewardType.DEVICES,
        PromocodeRewardType.SUBSCRIPTION,
    }
)


def _status(code: PromocodeDto, now: datetime) -> PromocodeStatus:
    if not code.is_active:
        return PromocodeStatus.INACTIVE
    if code.expires_at is not None and code.expires_at <= now:
        return PromocodeStatus.EXPIRED
    return PromocodeStatus.ACTIVE


class GetPromocodeStatsUseCase(UseCase[AnalyticsPeriodQueryDto, PromocodeStatsDto]):
    required_permission = Permission.ANALYTICS_PROMOCODES_VIEW

    def __init__(
        self,
        user_stats: UserStatsRepository,
        promocode_repository: PromocodeRepository,
        transaction_stats: TransactionStatsRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        cache: AnalyticsCache,
    ) -> None:
        self._user_stats = user_stats
        self._promocode_repository = promocode_repository
        self._transaction_stats = transaction_stats
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._cache = cache

    async def _execute(self, actor: Actor, data: AnalyticsPeriodQueryDto) -> PromocodeStatsDto:
        return await self._cache.get_or_compute(
            "get_promocode_stats", data, PromocodeStatsDto, partial(self._compute, data)
        )

    async def _compute(self, data: AnalyticsPeriodQueryDto) -> PromocodeStatsDto:
        async with self._uow:
            now = datetime_now()
            period = resolve_period(
                data.period_from,
                data.period_to,
                earliest=await self._user_stats.earliest_registration(Role.USER),
                now=now,
            )
            rates = await self._pricing_repository.get_rate_table()
            codes = {c.id: c for c in await self._promocode_repository.list_all()}
            in_period = [
                a
                for a in await self._promocode_repository.list_activations(period.start, period.end)
                if a[0] in codes
            ]
            total = await self._promocode_repository.count_activations_by_promocode()

            activators = sorted({user_id for _, user_id, _ in in_period})
            payments: dict[int, list[tuple[datetime, Decimal]]] = defaultdict(list)
            for row in await self._transaction_stats.list_paid_by_users(activators, period.end):
                payments[row.user_id].append((row.paid_at, row.anchor_final_price))

            period_revenue = discount_revenue = discount_given = ZERO_AMOUNT
            for row in await self._transaction_stats.list_paid(period.start, period.end):
                amount = row.anchor_final_price
                period_revenue += amount
                if row.discount_percent > 0:
                    discount_revenue += amount
                    discount_given += row.user_discount_amount

            per_code: dict[int, list[tuple[int, datetime]]] = defaultdict(list)
            for promocode_id, user_id, at in in_period:
                per_code[promocode_id].append((user_id, at))

            rows: list[PromocodeRowDto] = []
            by_type: dict[PromocodeRewardType, int] = dict.fromkeys(PromocodeRewardType, 0)
            free_total = free_converted = 0
            for promocode_id, uses in per_code.items():
                code = codes[promocode_id]
                is_free = code.reward_type in _FREE_REWARD_TYPES
                converted = sum(
                    1 for user_id, at in uses if any(paid >= at for paid, _ in payments[user_id])
                )
                first_use: dict[int, datetime] = {}
                for u, at in uses:
                    if u not in first_use or at < first_use[u]:
                        first_use[u] = at
                revenue_after = sum(
                    (
                        amount
                        for u, at in first_use.items()
                        for paid, amount in payments[u]
                        if paid >= at
                    ),
                    start=ZERO_AMOUNT,
                )
                by_type[code.reward_type] += len(uses)
                if is_free:
                    free_total += len(uses)
                    free_converted += converted
                rows.append(
                    PromocodeRowDto(
                        promocode_id=promocode_id,
                        code=code.code,
                        reward_type=code.reward_type,
                        reward=code.reward,
                        reward_duration_days=code.reward_duration_days,
                        activations=len(uses),
                        total_activations=total.get(promocode_id, 0),
                        max_activations=code.max_activations,
                        revenue_after=round_cents(revenue_after),
                        conversion_rate=converted / len(uses) if is_free else None,
                        status=_status(code, now),
                    )
                )
            rows.sort(key=lambda r: (-r.activations, r.code))
            previous = period.previous
            return PromocodeStatsDto(
                period=AnalyticsPeriodInfoDto(
                    start=period.start,
                    end=period.end,
                    previous_start=previous.start,
                    previous_end=previous.end,
                ),
                report_currency=rates.anchor,
                activations=len(in_period),
                codes_used=len(rows),
                discount_given=round_cents(discount_given),
                revenue_with_discount=round_cents(discount_revenue),
                revenue_share=float(discount_revenue / period_revenue) if period_revenue else 0.0,
                free_reward_conversion=free_converted / free_total if free_total else 0.0,
                by_reward_type=[
                    RewardTypeCountDto(reward_type=t, activations=n) for t, n in by_type.items()
                ],
                codes=rows,
            )

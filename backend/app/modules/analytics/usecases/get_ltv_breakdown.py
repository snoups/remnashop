from collections import defaultdict
from collections.abc import Mapping
from decimal import Decimal
from functools import partial
from typing import Final, Optional

from app.core.actor import Actor
from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.money import round_cents
from app.core.utils.time import datetime_now
from app.modules.advertising import AdLinkRepository
from app.modules.analytics.cache import AnalyticsCache
from app.modules.analytics.dto import LtvBreakdownDto, LtvGroupDto, TopPayerDto
from app.modules.analytics.sources import SourceKind, UserSource, resolve_sources
from app.modules.pricing import PricingRepository
from app.modules.referrals import ReferralRepository
from app.modules.subscriptions import LiveSubscriptionDto, SubscriptionStatsRepository
from app.modules.transactions import PayerSummaryDto, TransactionStatsRepository
from app.modules.users import UserRepository

_TOP_LIMIT: Final[int] = 10


_GroupId = tuple[str, Optional[SourceKind], Optional[int]]


def _source_group(source: UserSource) -> _GroupId:
    if source.kind == SourceKind.AD_LINK:
        return (source.ad_link_name or "", source.kind, source.ad_link_id)
    return (source.kind.value, source.kind, None)


def _groups(totals: dict[int, Decimal], group_of: Mapping[int, _GroupId]) -> list[LtvGroupDto]:
    sums: dict[_GroupId, Decimal] = defaultdict(lambda: ZERO_AMOUNT)
    counts: dict[_GroupId, int] = defaultdict(int)
    for user_id, total in totals.items():
        sums[group_of[user_id]] += total
        counts[group_of[user_id]] += 1
    ordered = sorted(counts, key=lambda g: (-round_cents(sums[g] / counts[g]), g[0], g[2] or 0))
    return [
        LtvGroupDto(
            key=key, source=source, customers=counts[g], avg_ltv=round_cents(sums[g] / counts[g])
        )
        for g in ordered
        for key, source, _ in (g,)
    ]


def _current_plans(live: list[LiveSubscriptionDto]) -> dict[int, list[str]]:
    plans: dict[int, list[str]] = {}
    for row in sorted(live, key=lambda row: row.expire_at, reverse=True):
        if not row.is_trial:
            plans.setdefault(row.user_id, []).append(row.plan_name)
    return plans


class GetLtvBreakdownUseCase(UseCase[None, LtvBreakdownDto]):
    required_permission = Permission.ANALYTICS_LTV_BREAKDOWN_VIEW

    def __init__(
        self,
        transaction_stats: TransactionStatsRepository,
        subscription_stats: SubscriptionStatsRepository,
        user_repository: UserRepository,
        ad_link_repository: AdLinkRepository,
        referral_repository: ReferralRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        cache: AnalyticsCache,
    ) -> None:
        self._transaction_stats = transaction_stats
        self._subscription_stats = subscription_stats
        self._user_repository = user_repository
        self._ad_link_repository = ad_link_repository
        self._referral_repository = referral_repository
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._cache = cache

    async def _top_payers(
        self, totals: dict[int, Decimal], payers: dict[int, PayerSummaryDto]
    ) -> list[TopPayerDto]:
        # a customer ranking: staff purchases are not shown to anyone
        staff = await self._user_repository.list_staff_ids()
        customers = [user_id for user_id in totals if user_id not in staff]
        top = sorted(customers, key=lambda user_id: (-totals[user_id], user_id))[:_TOP_LIMIT]
        users = {u.id: u for u in await self._user_repository.list_by_ids(top)}
        plans = _current_plans(await self._subscription_stats.list_live())
        return [
            TopPayerDto(
                user_id=user_id,
                name=users[user_id].name if user_id in users else "",
                username=users[user_id].username if user_id in users else None,
                current_plans=plans.get(user_id, []),
                payments=payers[user_id].payments,
                spent=round_cents(totals[user_id]),
                last_paid_at=payers[user_id].last_paid_at,
            )
            for user_id in top
        ]

    async def _execute(self, actor: Actor, data: None) -> LtvBreakdownDto:
        return await self._cache.get_or_compute(
            "get_ltv_breakdown", data, LtvBreakdownDto, partial(self._compute, data)
        )

    async def _compute(self, data: None) -> LtvBreakdownDto:
        async with self._uow:
            rates = await self._pricing_repository.get_rate_table()
            payers = {
                p.user_id: p for p in await self._transaction_stats.payer_summaries(datetime_now())
            }
            totals = {user_id: p.spent for user_id, p in payers.items()}
            sources = await resolve_sources(
                list(totals), ad_links=self._ad_link_repository, referrals=self._referral_repository
            )
            source_groups = {user_id: _source_group(src) for user_id, src in sources.items()}
            plan_groups: dict[int, _GroupId] = {
                user_id: (p.first_plan_name, None, None) for user_id, p in payers.items()
            }
            return LtvBreakdownDto(
                report_currency=rates.anchor,
                by_first_plan=_groups(totals, plan_groups),
                by_source=_groups(totals, source_groups),
                top_payers=await self._top_payers(totals, payers),
            )

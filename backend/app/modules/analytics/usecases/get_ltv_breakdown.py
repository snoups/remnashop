from collections import defaultdict
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Optional

from app.core.actor import Actor
from app.core.constants import ONE_CENT
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.advertising import AdLinkRepository
from app.modules.analytics.dto import LtvBreakdownDto, LtvGroupDto, TopPayerDto
from app.modules.analytics.sources import SourceKind, UserSource, resolve_sources
from app.modules.pricing import PricingRepository
from app.modules.referrals import ReferralRepository
from app.modules.subscriptions import LiveSubscriptionDto, SubscriptionStatsRepository
from app.modules.transactions import PaidTransactionDto, TransactionStatsRepository
from app.modules.users import UserRepository

_ZERO: Final[Decimal] = Decimal(0)
_TOP_LIMIT: Final[int] = 10


_GroupId = tuple[str, Optional[SourceKind], Optional[int]]


def _cents(value: Decimal) -> Decimal:
    return value.quantize(ONE_CENT, rounding=ROUND_HALF_UP)


def _source_group(source: UserSource) -> _GroupId:
    if source.kind == SourceKind.AD_LINK:
        return (source.ad_link_name or "", source.kind, source.ad_link_id)
    return (source.kind.value, source.kind, None)


def _groups(totals: dict[int, Decimal], group_of: Mapping[int, _GroupId]) -> list[LtvGroupDto]:
    sums: dict[_GroupId, Decimal] = defaultdict(lambda: _ZERO)
    counts: dict[_GroupId, int] = defaultdict(int)
    for user_id, total in totals.items():
        sums[group_of[user_id]] += total
        counts[group_of[user_id]] += 1
    ordered = sorted(counts, key=lambda g: (-_cents(sums[g] / counts[g]), g[0], g[2] or 0))
    return [
        LtvGroupDto(
            key=key, source=source, customers=counts[g], avg_ltv=_cents(sums[g] / counts[g])
        )
        for g in ordered
        for key, source, _ in (g,)
    ]


def _current_plans(live: list[LiveSubscriptionDto]) -> dict[int, str]:
    latest: dict[int, LiveSubscriptionDto] = {}
    for row in live:
        if not row.is_trial and (
            row.user_id not in latest or row.expire_at > latest[row.user_id].expire_at
        ):
            latest[row.user_id] = row
    return {user_id: row.plan_name for user_id, row in latest.items()}


def _per_user(
    paid: list[PaidTransactionDto],
) -> tuple[dict[int, Decimal], dict[int, int], dict[int, PaidTransactionDto]]:
    totals: dict[int, Decimal] = {}
    payments: dict[int, int] = {}
    last: dict[int, PaidTransactionDto] = {}
    for row in paid:  # list_paid is ordered by paid_at
        totals[row.user_id] = totals.get(row.user_id, _ZERO) + row.anchor_final_price
        payments[row.user_id] = payments.get(row.user_id, 0) + 1
        last[row.user_id] = row
    return totals, payments, last


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
    ) -> None:
        self._transaction_stats = transaction_stats
        self._subscription_stats = subscription_stats
        self._user_repository = user_repository
        self._ad_link_repository = ad_link_repository
        self._referral_repository = referral_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _top_payers(
        self,
        totals: dict[int, Decimal],
        payments: dict[int, int],
        last: dict[int, PaidTransactionDto],
    ) -> list[TopPayerDto]:
        top = sorted(totals, key=lambda user_id: (-totals[user_id], user_id))[:_TOP_LIMIT]
        users = {u.id: u for u in await self._user_repository.list_by_ids(top)}
        plans = _current_plans(await self._subscription_stats.list_live())
        return [
            TopPayerDto(
                user_id=user_id,
                name=users[user_id].name if user_id in users else "",
                username=users[user_id].username if user_id in users else None,
                current_plan=plans.get(user_id),
                payments=payments[user_id],
                spent=_cents(totals[user_id]),
                last_paid_at=last[user_id].paid_at,
            )
            for user_id in top
        ]

    async def _execute(self, actor: Actor, data: None) -> LtvBreakdownDto:
        async with self._uow:
            rates = await self._pricing_repository.get_rate_table()
            paid = await self._transaction_stats.list_paid(None, datetime_now())
            totals, payments, last = _per_user(paid)
            first_plan: dict[int, str] = {}
            for row in paid:
                first_plan.setdefault(row.user_id, row.plan_name)
            sources = await resolve_sources(
                list(totals), ad_links=self._ad_link_repository, referrals=self._referral_repository
            )
            source_groups = {user_id: _source_group(src) for user_id, src in sources.items()}
            plan_groups: dict[int, _GroupId] = {u: (n, None, None) for u, n in first_plan.items()}
            return LtvBreakdownDto(
                report_currency=rates.anchor,
                by_first_plan=_groups(totals, plan_groups),
                by_source=_groups(totals, source_groups),
                top_payers=await self._top_payers(totals, payments, last),
            )

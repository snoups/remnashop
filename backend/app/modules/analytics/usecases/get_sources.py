from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Optional

from app.core.actor import Actor
from app.core.constants import ONE_CENT
from app.core.db.uow import UnitOfWork
from app.core.enums import ReferralRewardType, Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.advertising import AdLinkRepository
from app.modules.analytics.aggregates import report_amount
from app.modules.analytics.dto import (
    AnalyticsPeriodInfoDto,
    AnalyticsPeriodQueryDto,
    ReferralPaybackDto,
    SourceRowDto,
    SourcesDto,
    TopReferrerDto,
)
from app.modules.analytics.period import resolve_period
from app.modules.analytics.sources import SourceKind, UserSource, resolve_sources
from app.modules.pricing import PricingRepository
from app.modules.referrals import ReferralRepository
from app.modules.transactions import TransactionStatsRepository
from app.modules.users import UserRepository, UserStatsRepository

_ZERO: Final[Decimal] = Decimal(0)
_TOP_LIMIT: Final[int] = 10
_DEEP_LEVEL: Final[int] = 2


def _cents(value: Decimal) -> Decimal:
    return value.quantize(ONE_CENT, rounding=ROUND_HALF_UP)


def _row(
    kind: SourceKind,
    ad_link_id: Optional[int],
    name: Optional[str],
    user_ids: list[int],
    totals: dict[int, Decimal],
) -> SourceRowDto:
    payers = [user_id for user_id in user_ids if user_id in totals]
    revenue = sum((totals[user_id] for user_id in payers), start=_ZERO)
    return SourceRowDto(
        source=kind,
        ad_link_id=ad_link_id,
        name=name,
        registrations=len(user_ids),
        payers=len(payers),
        conversion_rate=len(payers) / len(user_ids) if user_ids else 0.0,
        revenue=_cents(revenue),
        revenue_per_payer=_cents(revenue / len(payers)) if payers else _ZERO,
    )


def _channels(
    sources: dict[int, UserSource], totals: dict[int, Decimal]
) -> tuple[list[SourceRowDto], list[SourceRowDto]]:
    by_kind: dict[SourceKind, list[int]] = {kind: [] for kind in SourceKind}
    by_link: dict[int, list[int]] = defaultdict(list)
    names: dict[int, Optional[str]] = {}
    for user_id, source in sources.items():
        by_kind[source.kind].append(user_id)
        if source.ad_link_id is not None:
            by_link[source.ad_link_id].append(user_id)
            names[source.ad_link_id] = source.ad_link_name
    channels = [_row(kind, None, None, by_kind[kind], totals) for kind in SourceKind]
    links = [
        _row(SourceKind.AD_LINK, link_id, names[link_id], ids, totals)
        for link_id, ids in by_link.items()
    ]
    links.sort(key=lambda row: (-row.revenue, row.ad_link_id or 0))
    return channels, links


class GetSourcesUseCase(UseCase[AnalyticsPeriodQueryDto, SourcesDto]):
    required_permission = Permission.ANALYTICS_SOURCES_VIEW

    def __init__(
        self,
        user_stats: UserStatsRepository,
        user_repository: UserRepository,
        transaction_stats: TransactionStatsRepository,
        ad_link_repository: AdLinkRepository,
        referral_repository: ReferralRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_stats = user_stats
        self._user_repository = user_repository
        self._transaction_stats = transaction_stats
        self._ad_link_repository = ad_link_repository
        self._referral_repository = referral_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _top_referrers(
        self,
        edges: dict[int, tuple[Optional[int], int]],
        cohort: set[int],
        totals: dict[int, Decimal],
        days: dict[int, int],
    ) -> list[TopReferrerDto]:
        referred: dict[int, list[int]] = defaultdict(list)
        for user_id, (referrer_id, _) in edges.items():
            if referrer_id is not None and (user_id in cohort or user_id in totals):
                referred[referrer_id].append(user_id)
        revenue = {
            referrer: sum((totals.get(u, _ZERO) for u in ids), start=_ZERO)
            for referrer, ids in referred.items()
        }
        top = sorted(referred, key=lambda referrer: (-revenue[referrer], referrer))[:_TOP_LIMIT]
        users = {u.id: u for u in await self._user_repository.list_by_ids(top)}
        return [
            TopReferrerDto(
                user_id=referrer,
                name=users[referrer].name if referrer in users else "",
                invited=sum(1 for u in referred[referrer] if u in cohort),
                paid=sum(1 for u in referred[referrer] if u in totals),
                revenue=_cents(revenue[referrer]),
                reward_days=days.get(referrer, 0),
            )
            for referrer in top
        ]

    async def _execute(self, actor: Actor, data: AnalyticsPeriodQueryDto) -> SourcesDto:
        async with self._uow:
            now = datetime_now()
            period = resolve_period(
                data.period_from,
                data.period_to,
                earliest=await self._user_stats.earliest_registration(Role.USER),
                now=now,
            )
            rates = await self._pricing_repository.get_rate_table()
            cohort = [
                user_id
                for user_id, _ in await self._user_stats.list_registrations(
                    period.start, period.end, Role.USER
                )
            ]
            totals: dict[int, Decimal] = {}
            for row in await self._transaction_stats.list_paid_by_users(cohort, now):
                totals[row.user_id] = totals.get(row.user_id, _ZERO) + report_amount(
                    row.final_price, row.currency, rates
                )
            sources = await resolve_sources(
                cohort, ad_links=self._ad_link_repository, referrals=self._referral_repository
            )
            channels, ad_links = _channels(sources, totals)

            reward_days: dict[int, int] = defaultdict(int)
            total_days = total_points = 0
            for referrer_id, kind, amount in await self._referral_repository.list_rewards(
                period.start, period.end
            ):
                if kind == ReferralRewardType.EXTRA_DAYS:
                    total_days += int(amount)
                    if referrer_id is not None:
                        reward_days[referrer_id] += int(amount)
                else:
                    total_points += int(amount)
            edges = {
                referred_id: (referrer_id, level)
                for referred_id, referrer_id, level in await self._referral_repository.list_edges()
            }
            period_totals: dict[int, Decimal] = {}
            for row in await self._transaction_stats.list_paid(period.start, period.end):
                if row.user_id in edges:
                    period_totals[row.user_id] = period_totals.get(row.user_id, _ZERO) + (
                        report_amount(row.final_price, row.currency, rates)
                    )
            referred_revenue = sum(period_totals.values(), start=_ZERO)
            deep_revenue = sum(
                (amount for u, amount in period_totals.items() if edges[u][1] >= _DEEP_LEVEL),
                start=_ZERO,
            )
            previous = period.previous
            return SourcesDto(
                period=AnalyticsPeriodInfoDto(
                    start=period.start,
                    end=period.end,
                    previous_start=previous.start,
                    previous_end=previous.end,
                ),
                report_currency=rates.anchor,
                channels=channels,
                ad_links=ad_links,
                referral=ReferralPaybackDto(
                    referred_revenue=_cents(referred_revenue),
                    reward_days=total_days,
                    reward_points=total_points,
                    referrers=len({edges[u][0] for u in period_totals} - {None}),
                    deep_levels_revenue_share=float(deep_revenue / referred_revenue)
                    if referred_revenue
                    else 0.0,
                ),
                top_referrers=await self._top_referrers(
                    edges, set(cohort), period_totals, reward_days
                ),
            )

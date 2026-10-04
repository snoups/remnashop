from typing import Final, Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.advertising import AdLinkRepository
from app.modules.analytics.dto import (
    AnalyticsPeriodInfoDto,
    AnalyticsPeriodQueryDto,
    FunnelDto,
    FunnelSourceRowDto,
    FunnelStepDto,
)
from app.modules.analytics.period import resolve_period
from app.modules.analytics.sources import SourceKind, resolve_sources
from app.modules.referrals import ReferralRepository
from app.modules.subscriptions import SubscriptionStatsRepository
from app.modules.transactions import TransactionRepository
from app.modules.users import UserStatsRepository

_STEP_KEYS: Final[tuple[str, str, str, str]] = (
    "registered",
    "connected",
    "first_paid",
    "repeat_paid",
)


class GetFunnelUseCase(UseCase[AnalyticsPeriodQueryDto, FunnelDto]):
    required_permission = Permission.ANALYTICS_FUNNEL_VIEW

    def __init__(
        self,
        user_stats: UserStatsRepository,
        subscription_stats: SubscriptionStatsRepository,
        transaction_repository: TransactionRepository,
        ad_links: AdLinkRepository,
        referrals: ReferralRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_stats = user_stats
        self._subscription_stats = subscription_stats
        self._transaction_repository = transaction_repository
        self._ad_links = ad_links
        self._referrals = referrals
        self._uow = uow

    async def _execute(self, actor: Actor, data: AnalyticsPeriodQueryDto) -> FunnelDto:
        async with self._uow:
            period = resolve_period(
                data.period_from,
                data.period_to,
                earliest=await self._user_stats.earliest_registration(Role.USER),
                now=datetime_now(),
            )
            previous = period.previous
            registered = [
                user_id
                for user_id, _ in await self._user_stats.list_registrations(
                    period.start, period.end, Role.USER
                )
            ]
            paid = await self._transaction_repository.list_user_ids_with_paid_order(registered)
            # first_connected_at is only tracked from now on; a payer has used the product
            connected = await self._subscription_stats.list_user_ids_connected(registered) | paid
            repeat = await self._transaction_repository.list_user_ids_with_multiple_paid_orders(
                list(paid)
            )
            paid_via_trial = await self._subscription_stats.list_user_ids_with_trial(list(paid))

            counts = [len(registered), len(connected), len(paid), len(repeat)]
            start = counts[0]
            steps = [
                FunnelStepDto(
                    key=_STEP_KEYS[i],
                    count=counts[i],
                    pct_of_start=(counts[i] / start) if start else 0.0,
                    pct_of_prev=(
                        1.0 if i == 0 else ((counts[i] / counts[i - 1]) if counts[i - 1] else 0.0)
                    ),
                )
                for i in range(len(_STEP_KEYS))
            ]

            sources = await resolve_sources(
                registered, ad_links=self._ad_links, referrals=self._referrals
            )
            groups: dict[tuple[SourceKind, Optional[int]], list[int]] = {}
            names: dict[tuple[SourceKind, Optional[int]], Optional[str]] = {}
            for user_id in registered:
                source = sources[user_id]
                key = (source.kind, source.ad_link_id)
                groups.setdefault(key, []).append(user_id)
                names[key] = source.ad_link_name
            by_source = sorted(
                (
                    FunnelSourceRowDto(
                        source=kind,
                        ad_link_id=ad_link_id,
                        name=names[(kind, ad_link_id)],
                        registered=len(members),
                        connected=len(connected.intersection(members)),
                        paid=len(paid.intersection(members)),
                        repeat_paid=len(repeat.intersection(members)),
                    )
                    for (kind, ad_link_id), members in groups.items()
                ),
                key=lambda row: (-row.registered, row.source, row.ad_link_id or 0),
            )
            return FunnelDto(
                period=AnalyticsPeriodInfoDto(
                    start=period.start,
                    end=period.end,
                    previous_start=previous.start,
                    previous_end=previous.end,
                ),
                steps=steps,
                paid_via_trial=len(paid_via_trial),
                by_source=by_source,
            )

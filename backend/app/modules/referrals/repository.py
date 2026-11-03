from datetime import datetime
from decimal import Decimal
from typing import Any, Final, Optional, cast

from sqlalchemy import (
    CTE,
    ColumnElement,
    CursorResult,
    Integer,
    Select,
    case,
    distinct,
    exists,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.constants import DEFAULT_PAGE_SIZE
from app.core.db.errors import constraint_name
from app.core.db.filters import in_ids
from app.core.db.models.referral import Referral
from app.core.db.models.referral_reward import ReferralReward
from app.core.db.models.referral_settings import ReferralSettings
from app.core.db.models.subscription import Subscription
from app.core.db.models.user import User
from app.core.db.partial_update import apply_partial_update
from app.core.db.singleton import SINGLETON_ID, get_or_create_singleton
from app.core.db.user_search import user_search_filter
from app.core.enums import ReferralLevel, ReferralRewardType, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.utils.time import datetime_now
from app.modules.referrals.dto import (
    DEFAULT_REWARD_AMOUNTS,
    DownlineEntryDto,
    ReferralDto,
    ReferralRewardDto,
    ReferralRewardTotalsDto,
    ReferralSettingsDto,
    ReferralSummaryDto,
    UpdateReferralSettingsDto,
)

# rewards never reach further up the chain than this
_MAX_DEPTH: Final[int] = max(ReferralLevel)


def _rewards_before(created_to: Optional[datetime]) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [ReferralReward.reversed_at.is_(None)]
    if created_to is not None:
        filters.append(ReferralReward.created_at < created_to)
    return filters


def _search_users(search: str, search_staff: bool) -> Select[tuple[int]]:
    # staff rows are hidden from callers without ADMINS_MANAGE; matching them would be an oracle
    query = select(User.id).where(user_search_filter(search, include_login=False))
    return query if search_staff else query.where(User.role == Role.USER)


def _visible_downline(column: ColumnElement[int], viewer_id: int) -> ColumnElement[bool]:
    # same rule as visible_user: staff rows are hidden, the viewer's own row is not
    return or_(column.in_(select(User.id).where(User.role == Role.USER)), column == viewer_id)


class ReferralRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: Referral) -> ReferralDto:
        return ReferralDto.model_validate(row, from_attributes=True)

    def _to_reward_dto(
        self, row: ReferralReward, buyer_id: Optional[int] = None
    ) -> ReferralRewardDto:
        return ReferralRewardDto.model_validate(row, from_attributes=True).model_copy(
            update={"buyer_id": buyer_id}
        )

    def _to_settings_dto(self, row: Optional[ReferralSettings]) -> ReferralSettingsDto:
        if row is None:
            return ReferralSettingsDto()
        return ReferralSettingsDto(
            id=row.id,
            enabled=row.enabled,
            max_level=row.max_level,
            accrual_strategy=row.accrual_strategy,
            reward_type=row.reward_type,
            reward_strategy=row.reward_strategy,
            reward_amounts={
                **DEFAULT_REWARD_AMOUNTS,
                **{int(k): Decimal(str(v)) for k, v in row.reward_amounts.items()},
            },
            days_require_paid_subscription=row.days_require_paid_subscription,
            invitee_reward_type=row.invitee_reward_type,
            invitee_reward_amount=row.invitee_reward_amount,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def find_by_referred_id(self, referred_id: int) -> Optional[ReferralDto]:
        stmt = select(Referral).where(Referral.referred_id == referred_id)
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row is not None else None

    async def has_referrer(self, user_id: int) -> bool:
        return await self.find_by_referred_id(user_id) is not None

    async def list_edges(
        self, referred_ids: Optional[list[int]] = None
    ) -> list[tuple[int, Optional[int], int]]:
        stmt = select(Referral.referred_id, Referral.referrer_id, Referral.level)
        if referred_ids is None:
            return list((await self.session.execute(stmt)).tuples().all())
        result: list[tuple[int, Optional[int], int]] = []
        rows = await self.session.execute(stmt.where(in_ids(Referral.referred_id, referred_ids)))
        result.extend(rows.tuples().all())
        return result

    async def create_referral(
        self, *, referrer_id: int, referred_id: int, level: int
    ) -> ReferralDto:
        row = Referral(referrer_id=referrer_id, referred_id=referred_id, level=level)
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as error:
            if constraint_name(error) != "uq_referrals_referred_id":
                raise
            raise ConflictError(
                f"User '{referred_id}' already has a referrer", code=ErrorCode.REFERRER_ALREADY_SET
            ) from error
        return self._to_dto(row)

    def _downline(self, referrer_id: int) -> CTE:
        # depth is relative to referrer_id; Referral.level is the edge's depth
        # from the chain's root, the same for every direct invitee
        downline = (
            select(
                Referral.id.label("id"),
                Referral.referred_id.label("referred_id"),
                Referral.referrer_id.label("parent_id"),
                Referral.created_at.label("created_at"),
                literal(1, Integer).label("depth"),
            )
            .where(Referral.referrer_id == referrer_id)
            .cte("downline", recursive=True)
        )
        child = aliased(Referral)
        return downline.union_all(
            select(
                child.id,
                child.referred_id,
                child.referrer_id,
                child.created_at,
                downline.c.depth + 1,
            ).where(child.referrer_id == downline.c.referred_id, downline.c.depth < _MAX_DEPTH)
        )

    async def count_by_level(
        self, referrer_id: int, *, hide_staff_from: Optional[int] = None
    ) -> dict[int, int]:
        downline = self._downline(referrer_id)
        stmt = select(downline.c.depth, func.count()).group_by(downline.c.depth)
        if hide_staff_from is not None:
            stmt = stmt.where(_visible_downline(downline.c.referred_id, hide_staff_from))
        rows = await self.session.execute(stmt)
        return {int(depth): int(count) for depth, count in rows.all()}

    async def list_downline(
        self,
        referrer_id: int,
        *,
        depth: Optional[int] = None,
        search: Optional[str] = None,
        search_staff: bool = True,
        hide_staff_from: Optional[int] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[DownlineEntryDto], int]:
        downline = self._downline(referrer_id)
        filters: list[ColumnElement[bool]] = []
        if hide_staff_from is not None:
            filters.append(_visible_downline(downline.c.referred_id, hide_staff_from))
        if depth is not None:
            filters.append(downline.c.depth == depth)
        if search:
            filters.append(downline.c.referred_id.in_(_search_users(search, search_staff)))

        total = await self.session.scalar(
            select(func.count()).select_from(downline).where(*filters)
        )
        stmt = (
            select(downline)
            .where(*filters)
            .order_by(downline.c.created_at.desc(), downline.c.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(stmt)).mappings().all()
        entries = [
            DownlineEntryDto(
                referred_id=row["referred_id"],
                parent_id=row["parent_id"],
                depth=row["depth"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
        return entries, int(total or 0)

    async def downline_user_ids(
        self, referrer_id: int, *, hide_staff_from: Optional[int] = None
    ) -> list[int]:
        downline = self._downline(referrer_id)
        stmt = select(downline.c.referred_id)
        if hide_staff_from is not None:
            stmt = stmt.where(_visible_downline(downline.c.referred_id, hide_staff_from))
        return list((await self.session.scalars(stmt)).all())

    async def downline_depths(self, referrer_id: int, user_ids: list[int]) -> dict[int, int]:
        if not user_ids:
            return {}
        downline = self._downline(referrer_id)
        stmt = select(downline.c.referred_id, downline.c.depth).where(
            in_ids(downline.c.referred_id, user_ids)
        )
        return {int(user_id): int(depth) for user_id, depth in (await self.session.execute(stmt))}

    async def reward_totals_by_buyer(
        self, referrer_id: int, buyer_ids: list[int]
    ) -> dict[int, dict[ReferralRewardType, Decimal]]:
        if not buyer_ids:
            return {}
        stmt = (
            select(Subscription.user_id, ReferralReward.type, func.sum(ReferralReward.amount))
            .join(Subscription, Subscription.id == ReferralReward.subscription_id)
            .where(
                ReferralReward.referrer_id == referrer_id,
                in_ids(Subscription.user_id, buyer_ids),
                ReferralReward.reversed_at.is_(None),
            )
            .group_by(Subscription.user_id, ReferralReward.type)
        )
        totals: dict[int, dict[ReferralRewardType, Decimal]] = {}
        for buyer_id, reward_type, amount in (await self.session.execute(stmt)).all():
            totals.setdefault(buyer_id, {})[reward_type] = Decimal(amount)
        return totals

    def _list_filters(
        self,
        *,
        level: Optional[int],
        created_from: Optional[datetime],
        search: Optional[str],
        has_rewards: Optional[bool],
        reward_type: Optional[ReferralRewardType],
        search_staff: bool = True,
        created_to: Optional[datetime] = None,
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = []
        if level is not None:
            filters.append(Referral.level == level)
        if created_from is not None:
            filters.append(Referral.created_at >= created_from)
        if created_to is not None:
            filters.append(Referral.created_at < created_to)
        if search:
            matching_users = _search_users(search, search_staff)
            filters.append(
                or_(
                    Referral.referred_id.in_(matching_users),
                    Referral.referrer_id.in_(matching_users),
                )
            )
        rewarded = exists().where(
            ReferralReward.referral_id == Referral.id, *_rewards_before(created_to)
        )
        if has_rewards is not None:
            filters.append(rewarded if has_rewards else ~rewarded)
        if reward_type is not None:
            filters.append(rewarded.where(ReferralReward.type == reward_type))
        return filters

    async def list_paginated(
        self,
        *,
        level: Optional[int] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        search: Optional[str] = None,
        has_rewards: Optional[bool] = None,
        reward_type: Optional[ReferralRewardType] = None,
        search_staff: bool = True,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[ReferralDto], int]:
        filters = self._list_filters(
            level=level,
            created_from=created_from,
            created_to=created_to,
            search=search,
            has_rewards=has_rewards,
            reward_type=reward_type,
            search_staff=search_staff,
        )

        count_stmt = select(func.count()).select_from(Referral).where(*filters)
        total = await self.session.scalar(count_stmt)

        order_by: list[ColumnElement[Any]] = []
        if search:
            # the searched user's own edge first, then the ones they invited
            matching_users = _search_users(search, search_staff)
            order_by.append(case((Referral.referred_id.in_(matching_users), 0), else_=1))
        order_by += [Referral.created_at.desc(), Referral.id.desc()]
        stmt = (
            select(Referral)
            .where(*filters)
            .order_by(*order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()
        return [self._to_dto(row) for row in rows], int(total or 0)

    async def summarize(
        self,
        *,
        level: Optional[int] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        search: Optional[str] = None,
        has_rewards: Optional[bool] = None,
        reward_type: Optional[ReferralRewardType] = None,
        search_staff: bool = True,
    ) -> ReferralSummaryDto:
        # created_to: the summary as it looked then, later referrals and rewards left out
        filters = self._list_filters(
            level=level,
            created_from=created_from,
            created_to=created_to,
            search=search,
            has_rewards=has_rewards,
            reward_type=reward_type,
            search_staff=search_staff,
        )
        rewarded = exists().where(
            ReferralReward.referral_id == Referral.id, *_rewards_before(created_to)
        )
        counts_stmt = select(
            func.count(),
            func.count(distinct(Referral.referrer_id)),
            func.count().filter(rewarded),
        ).where(*filters)
        total, referrers, rewarded_count = (await self.session.execute(counts_stmt)).one()

        amounts_stmt = (
            select(ReferralReward.type, func.sum(ReferralReward.amount))
            .where(
                ReferralReward.referral_id.in_(select(Referral.id).where(*filters)),
                *_rewards_before(created_to),
            )
            .group_by(ReferralReward.type)
        )
        amounts = {
            reward_type: Decimal(amount)
            for reward_type, amount in (await self.session.execute(amounts_stmt)).all()
        }
        return ReferralSummaryDto(
            total_count=int(total),
            referrers_count=int(referrers),
            rewarded_count=int(rewarded_count),
            reward_amounts=amounts,
        )

    async def reward_totals_by_referral(
        self, referral_ids: list[int]
    ) -> dict[int, ReferralRewardTotalsDto]:
        if not referral_ids:
            return {}
        stmt = (
            select(
                ReferralReward.referral_id,
                ReferralReward.type,
                func.count(),
                func.sum(ReferralReward.amount),
            )
            .where(
                in_ids(ReferralReward.referral_id, referral_ids),
                ReferralReward.reversed_at.is_(None),
            )
            .group_by(ReferralReward.referral_id, ReferralReward.type)
        )
        counts: dict[int, int] = {}
        amounts: dict[int, dict[ReferralRewardType, Decimal]] = {}
        for referral_id, reward_type, count, amount in (await self.session.execute(stmt)).all():
            counts[referral_id] = counts.get(referral_id, 0) + int(count)
            amounts.setdefault(referral_id, {})[reward_type] = Decimal(amount)
        return {
            referral_id: ReferralRewardTotalsDto(count=count, amounts=amounts[referral_id])
            for referral_id, count in counts.items()
        }

    async def list_rewards(
        self, start: datetime, end: datetime
    ) -> list[tuple[Optional[int], ReferralRewardType, Decimal]]:
        stmt = select(ReferralReward.referrer_id, ReferralReward.type, ReferralReward.amount).where(
            ReferralReward.created_at >= start,
            ReferralReward.created_at < end,
            ReferralReward.reversed_at.is_(None),
        )
        return list((await self.session.execute(stmt)).tuples().all())

    async def create_reward(
        self,
        *,
        referral_id: int,
        referrer_id: int,
        subscription_id: int,
        payment_key: str,
        type: ReferralRewardType,
        amount: Decimal,
    ) -> ReferralRewardDto:
        row = ReferralReward(
            referral_id=referral_id,
            referrer_id=referrer_id,
            subscription_id=subscription_id,
            payment_key=payment_key,
            type=type,
            amount=amount,
        )
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as error:
            if constraint_name(error) != "uq_referral_rewards_payment_referral":
                raise
            raise ConflictError(
                f"Reward already granted for payment '{payment_key}' and referral '{referral_id}'",
                code=ErrorCode.REFERRAL_REWARD_ALREADY_GRANTED,
            ) from error
        return self._to_reward_dto(row)

    async def list_active_rewards_by_payment_key(self, key: str) -> list[ReferralRewardDto]:
        rows = await self.session.scalars(
            select(ReferralReward)
            .where(ReferralReward.payment_key == key, ReferralReward.reversed_at.is_(None))
            .order_by(ReferralReward.id)
        )
        return [self._to_reward_dto(row) for row in rows]

    async def mark_reversed(self, reward_id: int) -> bool:
        result = await self.session.execute(
            update(ReferralReward)
            .where(ReferralReward.id == reward_id, ReferralReward.reversed_at.is_(None))
            .values(reversed_at=datetime_now())
        )
        return cast(CursorResult, result).rowcount > 0

    async def list_rewards_by_referrer(self, referrer_id: int) -> list[ReferralRewardDto]:
        # the buyer is the subscription's owner; the reward's referral edge is
        # this referrer's hop, not the purchase's
        stmt = (
            select(ReferralReward, Subscription.user_id)
            .outerjoin(Subscription, Subscription.id == ReferralReward.subscription_id)
            .where(ReferralReward.referrer_id == referrer_id, ReferralReward.reversed_at.is_(None))
            .order_by(ReferralReward.created_at.desc())
        )
        rows = await self.session.execute(stmt)
        return [self._to_reward_dto(row, buyer_id) for row, buyer_id in rows.all()]

    async def _get_or_create_settings(self) -> ReferralSettings:
        return await get_or_create_singleton(self.session, ReferralSettings, SINGLETON_ID)

    async def get_settings(self) -> ReferralSettingsDto:
        row = await self.session.get(ReferralSettings, SINGLETON_ID)
        return self._to_settings_dto(row)

    async def reset_settings(self) -> ReferralSettingsDto:
        row = await self.session.get(ReferralSettings, SINGLETON_ID)
        if row is not None:
            await self.session.delete(row)
            await self.session.flush()
        return self._to_settings_dto(None)

    async def update_settings(self, data: UpdateReferralSettingsDto) -> ReferralSettingsDto:
        row = await self._get_or_create_settings()

        apply_partial_update(row, data, skip=frozenset({"reward_amounts"}))
        if data.reward_amounts is not None:  # JSONB keys and values are strings
            row.reward_amounts = {str(k): str(v) for k, v in data.reward_amounts.items()}

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_settings_dto(row)

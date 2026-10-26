from datetime import datetime, timedelta
from typing import Final, Literal, Optional

from sqlalchemy import ColumnElement, Numeric, and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_PAGE_SIZE, INT32_MAX
from app.core.db.filters import in_ids
from app.core.db.models.addon_entitlement import AddOnEntitlement
from app.core.db.models.addon_grant_idempotency import AddOnGrantIdempotency
from app.core.db.models.subscription import Subscription
from app.core.db.models.user import User
from app.core.db.partial_update import apply_partial_update
from app.core.enums import AddOnType, Role, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import CooldownError, NotFoundError
from app.core.utils.time import datetime_now
from app.modules.subscriptions.domain import OWNED_STATUSES, SubscriptionState
from app.modules.subscriptions.dto import (
    AddOnEntitlementDto,
    CreateSubscriptionDto,
    PlanSnapshot,
    SubscriptionConfigUpdateDto,
    SubscriptionDto,
    UpdateSubscriptionDto,
    UpdateSubscriptionSquadsDto,
)

# pg_advisory_xact_lock namespace key, paired with a user_id (keys in
# modules/plans/repository.py are 8221938/8221939).
_SUBSCRIPTION_PURCHASE_CAP_LOCK_KEY: Final[int] = 8221940
RECONCILE_EXPIRED_WINDOW: Final[timedelta] = timedelta(days=30)

ResetColumn = Literal["device_single_reset_at", "device_all_reset_at", "link_reset_at"]


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _load_entitlements(
        self, subscription_ids: list[int]
    ) -> dict[int, list[AddOnEntitlementDto]]:
        if not subscription_ids:
            return {}

        result = await self.session.execute(
            select(AddOnEntitlement)
            .where(in_ids(AddOnEntitlement.subscription_id, subscription_ids))
            .order_by(AddOnEntitlement.id)
        )
        entitlements_by_subscription: dict[int, list[AddOnEntitlementDto]] = {}
        for row in result.scalars():
            entitlements_by_subscription.setdefault(row.subscription_id, []).append(
                AddOnEntitlementDto(
                    subscription_id=row.subscription_id,
                    addon_id=row.addon_id,
                    type=row.type,
                    amount=row.amount,
                    granted_at=row.granted_at,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        return entitlements_by_subscription

    def _to_dto(
        self, row: Subscription, entitlements: list[AddOnEntitlementDto]
    ) -> SubscriptionDto:
        traffic_bonus = sum(e.amount for e in entitlements if e.type == AddOnType.TRAFFIC)
        device_bonus = sum(e.amount for e in entitlements if e.type == AddOnType.DEVICES)
        return SubscriptionDto(
            id=row.id,
            user_id=row.user_id,
            remnawave_user_id=row.remnawave_user_id,
            status=row.status,
            is_trial=row.is_trial,
            traffic_limit=row.traffic_limit,
            device_limit=row.device_limit,
            # 0 = unlimited; an add-on on top must not turn it into a finite cap
            effective_traffic_limit=row.traffic_limit and row.traffic_limit + traffic_bonus,
            effective_device_limit=row.device_limit and row.device_limit + device_bonus,
            traffic_limit_strategy=row.traffic_limit_strategy,
            tag=row.tag,
            internal_squads=list(row.internal_squads),
            external_squad=row.external_squad,
            expire_at=row.expire_at,
            url=row.url,
            plan_snapshot=PlanSnapshot.from_json(dict(row.plan_snapshot)),
            device_single_reset_at=row.device_single_reset_at,
            device_all_reset_at=row.device_all_reset_at,
            link_reset_at=row.link_reset_at,
            paused_by_channel_leave=row.paused_by_channel_leave,
            addon_entitlements=entitlements,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _to_state(self, row: Subscription) -> SubscriptionState:
        return SubscriptionState(
            id=row.id,
            status=row.status,
            expire_at=row.expire_at,
            plan_snapshot=PlanSnapshot.from_json(dict(row.plan_snapshot)),
            traffic_limit=row.traffic_limit,
            device_limit=row.device_limit,
            traffic_limit_strategy=row.traffic_limit_strategy,
            internal_squads=list(row.internal_squads),
            external_squad=row.external_squad,
            is_trial=row.is_trial,
        )

    async def _get_or_raise(self, subscription_id: int) -> Subscription:
        row = await self.session.get(Subscription, subscription_id)
        if row is None:
            raise NotFoundError(
                f"Subscription '{subscription_id}' not found", code=ErrorCode.SUBSCRIPTION_NOT_FOUND
            )
        return row

    async def get_by_id(self, subscription_id: int) -> SubscriptionDto:
        row = await self._get_or_raise(subscription_id)
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

    async def list_all(self) -> list[SubscriptionDto]:
        result = await self.session.execute(select(Subscription).order_by(Subscription.id))
        rows = result.scalars().all()
        entitlements_by_subscription = await self._load_entitlements([row.id for row in rows])
        return [self._to_dto(row, entitlements_by_subscription.get(row.id, [])) for row in rows]

    async def list_paginated(
        self,
        *,
        status: Optional[SubscriptionStatus] = None,
        search: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        hide_staff_from: Optional[int] = None,
    ) -> tuple[list[SubscriptionDto], int]:
        # status=None means the live subscriptions: DELETED rows are routine
        # history (trial->paid conversions, plan changes), asked for explicitly
        filters: list[ColumnElement[bool]] = []
        if status is None:
            filters.append(Subscription.status != SubscriptionStatus.DELETED)
        else:
            filters.append(Subscription.status == status)
        if user_id is not None:
            filters.append(Subscription.user_id == user_id)
        if hide_staff_from is not None:
            # same rule as visible_user: staff rows are hidden, the viewer's own are not
            filters.append(
                or_(
                    Subscription.user_id.in_(select(User.id).where(User.role == Role.USER)),
                    Subscription.user_id == hide_staff_from,
                )
            )
        if search:
            pattern = f"%{search}%"
            search_filters: list[ColumnElement[bool]] = [
                Subscription.tag.ilike(pattern),
                Subscription.plan_snapshot["name"].astext.ilike(pattern),
            ]
            # id/user_id are Integer; a longer digit string would overflow asyncpg
            if search.isascii() and search.isdigit() and int(search) <= INT32_MAX:
                search_filters += [
                    Subscription.id == int(search),
                    Subscription.user_id == int(search),
                ]
            filters.append(or_(*search_filters))

        count_stmt = select(func.count()).select_from(Subscription).where(*filters)
        total = await self.session.scalar(count_stmt)

        stmt = (
            select(Subscription)
            .where(*filters)
            .order_by(Subscription.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()
        entitlements_by_subscription = await self._load_entitlements([row.id for row in rows])
        return [
            self._to_dto(row, entitlements_by_subscription.get(row.id, [])) for row in rows
        ], int(total or 0)

    async def get_active_by_user(self, user_id: int) -> list[SubscriptionDto]:
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id, Subscription.status.in_(OWNED_STATUSES))
            .order_by(Subscription.id)
        )
        rows = result.scalars().all()
        entitlements_by_subscription = await self._load_entitlements([row.id for row in rows])
        return [self._to_dto(row, entitlements_by_subscription.get(row.id, [])) for row in rows]

    async def get_live_by_user(self, user_id: int) -> list[SubscriptionDto]:
        # every row that still has a panel identity behind it, EXPIRED included
        result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status != SubscriptionStatus.DELETED,
            )
            .order_by(Subscription.id)
        )
        rows = result.scalars().all()
        entitlements_by_subscription = await self._load_entitlements([row.id for row in rows])
        return [self._to_dto(row, entitlements_by_subscription.get(row.id, [])) for row in rows]

    async def has_any_subscription(self, user_id: int, *, include_trial: bool = True) -> bool:
        # any row in any status: "has this user ever purchased", for the
        # NEW/EXISTING availability of plans and promocodes
        stmt = select(func.count()).select_from(Subscription).where(Subscription.user_id == user_id)
        if not include_trial:
            stmt = stmt.where(Subscription.is_trial.is_(False))
        count = await self.session.scalar(stmt)
        return bool(count)

    async def has_paid_subscription_before(
        self, user_id: int, subscription_id: Optional[int] = None
    ) -> bool:
        """Whether the user has a paid subscription created before subscription_id,
        if given: "is this the first paid one", which has_any_subscription can't
        answer once this one exists. A free one (100% discount, promocode grant)
        doesn't count."""
        price_paid = Subscription.plan_snapshot["price_paid"].astext.cast(Numeric)
        conditions = [
            Subscription.user_id == user_id,
            Subscription.is_trial.is_(False),
            price_paid > 0,
        ]
        if subscription_id is not None:
            # ids come from one sequence, so their order is creation order
            conditions.append(Subscription.id < subscription_id)
        stmt = select(func.count()).select_from(Subscription).where(*conditions)
        return bool(await self.session.scalar(stmt))

    async def list_non_terminal(self) -> list[SubscriptionDto]:
        # recently EXPIRED rows too: a renewal that reached the panel but not
        # our commit leaves the row EXPIRED until reconcile pulls it in
        result = await self.session.execute(
            select(Subscription)
            .where(
                or_(
                    Subscription.status.in_(OWNED_STATUSES),
                    and_(
                        Subscription.status == SubscriptionStatus.EXPIRED,
                        Subscription.expire_at > datetime_now() - RECONCILE_EXPIRED_WINDOW,
                    ),
                )
            )
            .order_by(Subscription.id)
        )
        rows = result.scalars().all()
        entitlements_by_subscription = await self._load_entitlements([row.id for row in rows])
        return [self._to_dto(row, entitlements_by_subscription.get(row.id, [])) for row in rows]

    async def get_by_id_for_update(self, subscription_id: int) -> SubscriptionDto:
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.id == subscription_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError(
                f"Subscription '{subscription_id}' not found", code=ErrorCode.SUBSCRIPTION_NOT_FOUND
            )
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

    async def get_active_by_user_for_update(self, user_id: int) -> list[SubscriptionDto]:
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id, Subscription.status.in_(OWNED_STATUSES))
            .order_by(Subscription.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        rows = result.scalars().all()
        entitlements_by_subscription = await self._load_entitlements([row.id for row in rows])
        return [self._to_dto(row, entitlements_by_subscription.get(row.id, [])) for row in rows]

    async def find_by_remnawave_user_id(self, remnawave_user_id: int) -> Optional[SubscriptionDto]:
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.remnawave_user_id == remnawave_user_id)
            .order_by(Subscription.status == SubscriptionStatus.DELETED, Subscription.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

    async def find_by_remnawave_user_id_for_update(
        self, remnawave_user_id: int
    ) -> Optional[SubscriptionDto]:
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.remnawave_user_id == remnawave_user_id)
            .order_by(Subscription.status == SubscriptionStatus.DELETED, Subscription.id.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

    async def acquire_purchase_cap_lock(self, user_id: int) -> None:
        """Serializes one user's purchases until the transaction ends. FOR UPDATE
        locks only existing rows, so two purchases could otherwise both read an
        under-cap count and both insert."""
        await self.session.execute(
            select(func.pg_advisory_xact_lock(_SUBSCRIPTION_PURCHASE_CAP_LOCK_KEY, user_id))
        )

    async def create(self, data: CreateSubscriptionDto) -> SubscriptionDto:
        row = Subscription(
            user_id=data.user_id,
            remnawave_user_id=data.remnawave_user_id,
            status=data.status,
            is_trial=data.is_trial,
            traffic_limit=data.traffic_limit,
            device_limit=data.device_limit,
            traffic_limit_strategy=data.traffic_limit_strategy,
            tag=data.tag,
            internal_squads=data.internal_squads,
            external_squad=data.external_squad,
            expire_at=data.expire_at,
            url=data.url,
            plan_snapshot=data.plan_snapshot.to_json(),
            device_single_reset_at=None,
            device_all_reset_at=None,
            link_reset_at=None,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row, [])

    async def update(self, data: UpdateSubscriptionDto) -> SubscriptionDto:
        # local row only; UpdateSubscriptionUseCase pushes it to the panel
        row = await self._get_or_raise(data.subscription_id)

        apply_partial_update(row, data, skip=frozenset({"subscription_id"}))

        await self.session.flush()
        await self.session.refresh(row)
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

    async def grant_entitlement(
        self,
        *,
        subscription_id: int,
        addon_id: Optional[int],
        addon_type: AddOnType,
        amount: int,
        idempotency_key: Optional[str] = None,
    ) -> SubscriptionDto:
        await self._get_or_raise(subscription_id)  # 404s before touching AddOnEntitlement

        if idempotency_key is not None:
            existing = await self.session.get(AddOnGrantIdempotency, idempotency_key)
            if existing is not None:
                return await self.get_by_id(subscription_id)

        entitlement = AddOnEntitlement(
            subscription_id=subscription_id,
            addon_id=addon_id,
            type=addon_type,
            amount=amount,
            granted_at=datetime_now(),
        )
        self.session.add(entitlement)
        if idempotency_key is not None:
            await self.session.flush()  # assigns entitlement.id
            self.session.add(
                AddOnGrantIdempotency(key=idempotency_key, entitlement_id=entitlement.id)
            )

        await self.session.flush()
        return await self.get_by_id(subscription_id)

    async def apply_panel_config(self, data: SubscriptionConfigUpdateDto) -> SubscriptionDto:
        row = await self._get_or_raise(data.subscription_id)
        row.url = data.url
        row.traffic_limit = data.traffic_limit
        row.device_limit = data.device_limit
        row.traffic_limit_strategy = data.traffic_limit_strategy
        row.tag = data.tag
        row.internal_squads = list(data.internal_squads)
        row.external_squad = data.external_squad
        if data.removed_addon_types:
            await self.session.execute(
                delete(AddOnEntitlement).where(
                    AddOnEntitlement.subscription_id == data.subscription_id,
                    AddOnEntitlement.type.in_(data.removed_addon_types),
                )
            )
        await self.session.flush()
        await self.session.refresh(row)
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

    async def update_squads(self, data: UpdateSubscriptionSquadsDto) -> SubscriptionDto:
        # local row only; UpdateSubscriptionSquadsUseCase pushes it to the panel
        row = await self._get_or_raise(data.subscription_id)
        row.internal_squads = data.internal_squads
        row.external_squad = data.external_squad

        await self.session.flush()
        await self.session.refresh(row)
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

    async def mark_deleted(self, subscription_id: int) -> SubscriptionDto:
        row = await self._get_or_raise(subscription_id)
        row.status = self._to_state(row).mark_deleted().status

        await self.session.flush()
        await self.session.refresh(row)
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

    async def claim_reset(
        self, subscription_id: int, column: ResetColumn, cooldown: timedelta
    ) -> Optional[datetime]:
        # stamped before the panel call, under the row lock: a concurrent tap
        # waits here and then sees the new stamp. Returns the old one for a refund.
        row = await self.session.scalar(
            select(Subscription)
            .where(Subscription.id == subscription_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise NotFoundError(
                f"Subscription '{subscription_id}' not found", code=ErrorCode.SUBSCRIPTION_NOT_FOUND
            )
        previous: Optional[datetime] = getattr(row, column)
        now = datetime_now()
        if previous is not None and now < previous + cooldown:
            raise CooldownError(previous + cooldown)
        setattr(row, column, now)
        await self.session.flush()
        return previous

    async def set_reset_at(
        self, subscription_id: int, column: ResetColumn, value: Optional[datetime]
    ) -> None:
        row = await self._get_or_raise(subscription_id)
        setattr(row, column, value)
        await self.session.flush()

    async def set_paused_by_channel_leave(self, subscription_id: int, paused: bool) -> None:
        row = await self._get_or_raise(subscription_id)
        row.paused_by_channel_leave = paused
        await self.session.flush()

    async def set_url(self, subscription_id: int, url: str) -> SubscriptionDto:
        row = await self._get_or_raise(subscription_id)
        row.url = url
        await self.session.flush()
        await self.session.refresh(row)
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

    async def set_first_connected_at(self, remnawave_user_id: int, at: datetime) -> None:
        await self.session.execute(
            update(Subscription)
            .where(
                Subscription.remnawave_user_id == remnawave_user_id,
                Subscription.status != SubscriptionStatus.DELETED,
                Subscription.first_connected_at.is_(None),
            )
            .values(first_connected_at=at)
        )

    async def apply_state(self, state: SubscriptionState) -> SubscriptionDto:
        row = await self._get_or_raise(state.id)
        row.status = state.status
        row.expire_at = state.expire_at
        row.plan_snapshot = state.plan_snapshot.to_json()
        # only SubscriptionLifecycleService calls apply_state, and neither of
        # its methods changes these fields, so this rewrites the same values
        row.traffic_limit = state.traffic_limit
        row.device_limit = state.device_limit
        row.traffic_limit_strategy = state.traffic_limit_strategy
        row.internal_squads = state.internal_squads
        row.external_squad = state.external_squad
        row.is_trial = state.is_trial

        await self.session.flush()
        await self.session.refresh(row)
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

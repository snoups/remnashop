from datetime import datetime
from typing import Final, Optional, cast

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.addon_entitlement import AddOnEntitlement
from app.core.db.models.addon_grant_idempotency import AddOnGrantIdempotency
from app.core.db.models.subscription import Subscription
from app.core.db.models.subscription_purchase_idempotency import SubscriptionPurchaseIdempotency
from app.core.enums import AddOnType, SubscriptionStatus
from app.core.exceptions import NotFoundError
from app.core.utils.time import datetime_now
from app.modules.subscriptions.domain import SubscriptionState
from app.modules.subscriptions.dto import (
    DEFAULT_PAGE_SIZE,
    AddOnEntitlementDto,
    CreateSubscriptionDto,
    PlanSnapshot,
    SubscriptionDto,
    UpdateSubscriptionDto,
    UpdateSubscriptionSquadsDto,
)

_ACTIVE_STATUSES: Final[tuple[SubscriptionStatus, ...]] = (
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.DISABLED,
    SubscriptionStatus.LIMITED,
)

# Arbitrary fixed namespace key for pg_advisory_xact_lock, paired with a
# user_id as the second key -- matches the existing convention in
# modules/plans/repository.py (_PLAN_ORDER_LOCK_KEY = 8221938,
# _PLAN_DURATIONS_LOCK_KEY = 8221939).
_SUBSCRIPTION_PURCHASE_CAP_LOCK_KEY: Final[int] = 8221940


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
            .where(AddOnEntitlement.subscription_id.in_(subscription_ids))
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
            effective_traffic_limit=row.traffic_limit + traffic_bonus,
            effective_device_limit=row.device_limit + device_bonus,
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
            raise NotFoundError(f"Subscription '{subscription_id}' not found")
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
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[SubscriptionDto], int]:
        # status=None means "the live subscriptions", not "every row ever" --
        # DELETED rows are now routine history (trial->paid conversions,
        # plan CHANGEs), not just the rare explicit-delete case this default
        # was written around. Pass status=DELETED explicitly to see them.
        if status is None:
            filters = [Subscription.status != SubscriptionStatus.DELETED]
        else:
            filters = [Subscription.status == status]

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
            .where(Subscription.user_id == user_id, Subscription.status.in_(_ACTIVE_STATUSES))
            .order_by(Subscription.id)
        )
        rows = result.scalars().all()
        entitlements_by_subscription = await self._load_entitlements([row.id for row in rows])
        return [self._to_dto(row, entitlements_by_subscription.get(row.id, [])) for row in rows]

    async def get_single_active_subscription_or_raise(self, user_id: int) -> SubscriptionDto:
        active = await self.get_active_by_user(user_id)
        if not active:
            raise NotFoundError(f"No active subscription for user '{user_id}'")
        return active[0]

    async def has_any_subscription(self, user_id: int, *, include_trial: bool = True) -> bool:
        # Any row ever, regardless of status (including DELETED/EXPIRED) --
        # this answers "has this user ever purchased", not "does one still
        # work". Backs PlanAvailability.NEW/EXISTING and
        # PromocodeAvailability.NEW/EXISTING alike (matches main's own
        # UserDao.has_any_subscription).
        stmt = select(func.count()).select_from(Subscription).where(Subscription.user_id == user_id)
        if not include_trial:
            stmt = stmt.where(Subscription.is_trial.is_(False))
        count = await self.session.scalar(stmt)
        return bool(count)

    async def get_by_remnawave_user_id(self, remnawave_user_id: int) -> Optional[SubscriptionDto]:
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.remnawave_user_id == remnawave_user_id)
            .order_by(Subscription.status == SubscriptionStatus.DELETED, Subscription.id.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

    async def list_non_terminal(self) -> list[SubscriptionDto]:
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.status.in_(_ACTIVE_STATUSES))
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
            raise NotFoundError(f"Subscription '{subscription_id}' not found")
        entitlements_by_subscription = await self._load_entitlements([row.id])
        return self._to_dto(row, entitlements_by_subscription.get(row.id, []))

    async def get_active_by_user_for_update(self, user_id: int) -> list[SubscriptionDto]:
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id, Subscription.status.in_(_ACTIVE_STATUSES))
            .order_by(Subscription.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        rows = result.scalars().all()
        entitlements_by_subscription = await self._load_entitlements([row.id for row in rows])
        return [self._to_dto(row, entitlements_by_subscription.get(row.id, [])) for row in rows]

    async def get_by_remnawave_user_id_for_update(
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
        """Serializes concurrent purchase attempts for the same user via a
        Postgres advisory lock (auto-released at transaction end). Necessary
        because `SELECT ... FOR UPDATE` in get_active_by_user_for_update only
        locks rows that already exist -- it cannot block a concurrent
        transaction from inserting a NEW row, so two concurrent purchases could
        both observe the same under-cap count and both proceed past it. This
        lock closes that gap: every purchase for a given user_id contends for
        the same (namespace, user_id) key before either reads the count."""
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
        # Local DB row only -- pushing the new limits to the Remnawave panel
        # is UpdateSubscriptionUseCase's job, after this commits.
        row = await self._get_or_raise(data.subscription_id)

        if data.tag is not None:
            row.tag = data.tag
        if data.traffic_limit is not None:
            row.traffic_limit = data.traffic_limit
        if data.device_limit is not None:
            row.device_limit = data.device_limit
        if data.traffic_limit_strategy is not None:
            row.traffic_limit_strategy = data.traffic_limit_strategy

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

    async def update_squads(self, data: UpdateSubscriptionSquadsDto) -> SubscriptionDto:
        # Local DB row only -- pushing the new squads to the Remnawave panel
        # is UpdateSubscriptionSquadsUseCase's job, after this commits.
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

    async def mark_device_single_reset(self, subscription_id: int) -> None:
        row = await self._get_or_raise(subscription_id)
        row.device_single_reset_at = datetime_now()
        await self.session.flush()

    async def mark_device_all_reset(self, subscription_id: int) -> None:
        row = await self._get_or_raise(subscription_id)
        row.device_all_reset_at = datetime_now()
        await self.session.flush()

    async def mark_link_reset(self, subscription_id: int, *, new_url: str) -> None:
        row = await self._get_or_raise(subscription_id)
        row.url = new_url
        row.link_reset_at = datetime_now()
        await self.session.flush()

    async def apply_state(self, state: SubscriptionState) -> SubscriptionDto:
        row = await self._get_or_raise(state.id)
        row.status = state.status
        row.expire_at = state.expire_at
        row.plan_snapshot = state.plan_snapshot.to_json()
        # apply_state is only reachable via SubscriptionLifecycleService's
        # sync_status/reactivate_on_renew, neither of which changes these
        # fields on the SubscriptionState they pass in -- always a no-op
        # write of the row's existing values.
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

    async def claim_idempotency_key(self, key: str) -> bool:
        result = await self.session.execute(
            pg_insert(SubscriptionPurchaseIdempotency)
            .values(key=key, subscription_id=None)
            .on_conflict_do_nothing(index_elements=["key"])
            .returning(SubscriptionPurchaseIdempotency.key)
        )
        claimed = result.scalar_one_or_none() is not None
        await self.session.flush()
        return claimed

    async def get_subscription_by_idempotency_key(self, key: str) -> Optional[SubscriptionDto]:
        row = await self.session.get(SubscriptionPurchaseIdempotency, key)
        if row is None or row.subscription_id is None:
            return None
        return await self.get_by_id(row.subscription_id)

    async def link_idempotency_key(self, key: str, subscription_id: int) -> None:
        row = await self.session.get(SubscriptionPurchaseIdempotency, key)
        if row is not None:
            row.subscription_id = subscription_id
            await self.session.flush()

    async def release_idempotency_key(self, key: str) -> None:
        row = await self.session.get(SubscriptionPurchaseIdempotency, key)
        if row is not None:
            await self.session.delete(row)
            await self.session.flush()

    async def delete_stale_idempotency_keys(self, cutoff: datetime) -> tuple[int, int]:
        purchase = await self.session.execute(
            delete(SubscriptionPurchaseIdempotency).where(
                SubscriptionPurchaseIdempotency.created_at < cutoff
            )
        )
        addon = await self.session.execute(
            delete(AddOnGrantIdempotency).where(AddOnGrantIdempotency.created_at < cutoff)
        )
        return cast(CursorResult, purchase).rowcount, cast(CursorResult, addon).rowcount

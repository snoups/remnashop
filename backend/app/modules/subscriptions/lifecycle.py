from datetime import datetime
from decimal import Decimal

from app.core.enums import SubscriptionStatus
from app.core.utils.time import datetime_now
from app.modules.subscriptions.domain import SubscriptionState
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository


def _dto_to_state(dto: SubscriptionDto) -> SubscriptionState:
    return SubscriptionState(
        id=dto.id,
        status=dto.status,
        expire_at=dto.expire_at,
        plan_snapshot=dto.plan_snapshot,
        traffic_limit=dto.traffic_limit,
        device_limit=dto.device_limit,
        traffic_limit_strategy=dto.traffic_limit_strategy,
        internal_squads=dto.internal_squads,
        external_squad=dto.external_squad,
        is_trial=dto.is_trial,
    )


class SubscriptionLifecycleService:
    """Every status/expire_at change to a Subscription goes through here;
    PurchaseSubscriptionUseCase and SyncSubscriptionStatusUseCase never write
    row.status/row.expire_at themselves."""

    def __init__(self, subscription_repository: SubscriptionRepository) -> None:
        self._subscription_repository = subscription_repository

    async def sync_status(
        self, subscription_id: int, target: SubscriptionStatus
    ) -> SubscriptionDto:
        dto = await self._subscription_repository.get_by_id_for_update(subscription_id)
        state = _dto_to_state(dto)
        new_state = state.sync_status(target)
        return await self._subscription_repository.apply_state(new_state)

    async def sync_expire_at(
        self, subscription_id: int, new_expire_at: datetime
    ) -> SubscriptionDto:
        dto = await self._subscription_repository.get_by_id_for_update(subscription_id)
        state = _dto_to_state(dto)
        new_state = state.sync_expire_at(new_expire_at)
        return await self._subscription_repository.apply_state(new_state)

    async def renew(
        self, subscription_id: int, new_expire_at: datetime, *, paid: Decimal, days: int
    ) -> SubscriptionDto:
        dto = await self._subscription_repository.get_by_id_for_update(subscription_id)
        state = _dto_to_state(dto)
        lapsed = state.expire_at <= datetime_now()
        new_state = state.reactivate_on_renew(new_expire_at).add_renewal_credit(
            paid, days, restart=lapsed
        )
        return await self._subscription_repository.apply_state(new_state)

    async def shorten_after_refund(
        self, subscription_id: int, *, days: int, paid: Decimal, now: datetime
    ) -> SubscriptionDto:
        dto = await self._subscription_repository.get_by_id_for_update(subscription_id)
        new_state = _dto_to_state(dto).shorten_after_refund(days, paid, now)
        return await self._subscription_repository.apply_state(new_state)

    async def restore_after_refund(self, subscription_id: int, now: datetime) -> SubscriptionDto:
        dto = await self._subscription_repository.get_by_id_for_update(subscription_id)
        new_state = _dto_to_state(dto).restore_after_refund(now)
        return await self._subscription_repository.apply_state(new_state)

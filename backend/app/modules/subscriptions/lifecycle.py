from datetime import datetime

from app.core.enums import SubscriptionStatus
from app.modules.subscriptions.domain import SubscriptionState
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository


def _dto_to_state(dto: SubscriptionDto) -> SubscriptionState:
    """Convert a SubscriptionDto to a SubscriptionState. Unlike the
    repository's _to_state (which parses plan_snapshot from raw JSON), the
    DTO already has plan_snapshot as a parsed PlanSnapshot object."""
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
    """Single collaborator for every status/expire_at-mutating operation on
    a Subscription -- PurchaseSubscriptionUseCase and
    SyncSubscriptionStatusUseCase both call into this instead of writing
    row.status/row.expire_at (or SubscriptionState) directly, so a future
    third caller reuses the same rules instead of re-deriving them."""

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

    async def renew(self, subscription_id: int, new_expire_at: datetime) -> SubscriptionDto:
        dto = await self._subscription_repository.get_by_id_for_update(subscription_id)
        state = _dto_to_state(dto)
        new_state = state.reactivate_on_renew(new_expire_at)
        return await self._subscription_repository.apply_state(new_state)

from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto, SyncSubscriptionStatusDto
from app.modules.subscriptions.events import SubscriptionStatusSyncedEvent
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class SyncSubscriptionStatusUseCase(UseCase[SyncSubscriptionStatusDto, Optional[SubscriptionDto]]):
    required_permission = None

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        lifecycle_service: SubscriptionLifecycleService,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._lifecycle_service = lifecycle_service

    async def _execute(
        self, actor: UserDto, data: SyncSubscriptionStatusDto
    ) -> Optional[SubscriptionDto]:
        async with self._uow:
            subscription = await self._subscription_repository.get_by_remnawave_user_id_for_update(
                data.remnawave_user_id
            )
            if subscription is None:
                return None
            if subscription.status is data.status:
                return subscription

            old_status = subscription.status
            subscription = await self._lifecycle_service.sync_status(subscription.id, data.status)

        if subscription.status is old_status:
            # sync_status() no-op'd (already DELETED) -- SubscriptionState's
            # own rule, not this usecase's; nothing changed, no event.
            return subscription

        await self._event_publisher.publish(
            SubscriptionStatusSyncedEvent(
                subscription_id=subscription.id,
                old_status=old_status.value,
                new_status=subscription.status.value,
                source=data.source,
            )
        )
        return subscription

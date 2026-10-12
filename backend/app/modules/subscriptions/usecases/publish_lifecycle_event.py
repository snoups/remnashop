from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.events import BaseEvent
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import PublishLifecycleEventDto
from app.modules.subscriptions.events import (
    SubscriptionExpiredEvent,
    SubscriptionExpiringEvent,
    SubscriptionTrafficLimitedEvent,
    SubscriptionTrafficThresholdEvent,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserRepository

_EXPIRED: Final[str] = "user.expired"
_EXPIRATION: Final[str] = "user.expiration"
_LIMITED: Final[str] = "user.limited"
_THRESHOLD: Final[str] = "user.bandwidth_usage_threshold_reached"


class PublishLifecycleEventUseCase(UseCase[PublishLifecycleEventDto, None]):
    # system-only: called from the Remnawave webhook handler
    required_permission = None

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: PublishLifecycleEventDto) -> None:
        # expiration with hours <= 0 means "expired N hours ago", which
        # user.expired already covers
        if data.webhook_event == _EXPIRATION and (data.hours is None or data.hours <= 0):
            return
        if data.webhook_event not in (_EXPIRATION, _EXPIRED, _LIMITED, _THRESHOLD):
            return

        async with self._uow:
            subscription = await self._subscription_repository.get_by_remnawave_user_id(
                data.remnawave_user_id
            )
            if subscription is None or subscription.status is SubscriptionStatus.DELETED:
                return
            owner = await self._user_repository.get_by_id(subscription.user_id)
            if owner is None:
                return

            event: BaseEvent
            if data.webhook_event == _EXPIRATION:
                assert data.hours is not None
                event = SubscriptionExpiringEvent(
                    user=owner, subscription_id=subscription.id, hours=data.hours
                )
            elif data.webhook_event == _EXPIRED:
                event = SubscriptionExpiredEvent(user=owner, subscription_id=subscription.id)
            elif data.webhook_event == _LIMITED:
                event = SubscriptionTrafficLimitedEvent(user=owner, subscription_id=subscription.id)
            else:
                event = SubscriptionTrafficThresholdEvent(
                    user=owner, subscription_id=subscription.id
                )
            await self._event_publisher.publish(event)

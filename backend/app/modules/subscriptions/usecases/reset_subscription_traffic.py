from loguru import logger
from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.eligibility import get_manageable_subscription, subscription_owner
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.panel import sync_status_after_reset
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserRepository


class ResetSubscriptionTrafficUseCase(UseCase[int, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_TRAFFIC_RESET

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        remnawave_sdk: RemnawaveSDK,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._remnawave_sdk = remnawave_sdk
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> SubscriptionDto:
        async with self._uow:
            subscription = await get_manageable_subscription(
                self._subscription_repository, self._user_repository, actor, data
            )

        panel_user = await self._remnawave_sdk.users.reset_user_traffic(
            subscription.remnawave_user_id
        )
        subscription = await sync_status_after_reset(
            self._subscription_repository, self._uow, subscription, panel_user
        )

        async with self._uow:
            subscriber = await subscription_owner(self._user_repository, subscription)
            await self._event_publisher.publish(
                SubscriptionEditedEvent(
                    actor=actor,
                    target=subscriber,
                    action="reset_traffic",
                    subscription_id=subscription.id,
                )
            )
        logger.info(f"{actor.log} Reset traffic of subscription '{subscription.id}'")
        return subscription

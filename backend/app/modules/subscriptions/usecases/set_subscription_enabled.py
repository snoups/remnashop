from loguru import logger
from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SetSubscriptionEnabledDto, SubscriptionDto
from app.modules.subscriptions.eligibility import get_live_subscription
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository


class SetSubscriptionEnabledUseCase(UseCase[SetSubscriptionEnabledDto, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_STATUS_MANAGE

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        lifecycle_service: SubscriptionLifecycleService,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._lifecycle_service = lifecycle_service
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: SetSubscriptionEnabledDto) -> SubscriptionDto:
        async with self._uow:
            subscription = await get_live_subscription(
                self._subscription_repository, data.subscription_id
            )

        users = self._remnawave_sdk.users
        if data.enabled:
            panel_status = (await users.enable_user(subscription.remnawave_user_id)).status
        else:
            panel_status = (await users.disable_user(subscription.remnawave_user_id)).status

        action = "enable" if data.enabled else "disable"
        async with self._uow:
            updated = await self._lifecycle_service.sync_status(
                subscription.id, SubscriptionStatus(panel_status)
            )
            await self._event_publisher.publish(
                SubscriptionEditedEvent(user=actor, action=action, subscription_id=subscription.id)
            )

        logger.info(f"{actor.log} Set subscription '{subscription.id}' {action}d")
        return updated

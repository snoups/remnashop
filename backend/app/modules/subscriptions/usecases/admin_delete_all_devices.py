from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import DeleteUserAllHwidDeviceRequestDto

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.eligibility import get_live_subscription
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.repository import SubscriptionRepository


class AdminDeleteAllDevicesUseCase(UseCase[int, None]):
    required_permission = Permission.SUBSCRIPTIONS_DEVICES_DELETE_ALL

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            subscription = await get_live_subscription(self._subscription_repository, data)
        await self._remnawave_sdk.hwid.delete_all_hwid_user(
            DeleteUserAllHwidDeviceRequestDto(user_id=subscription.remnawave_user_id)
        )
        async with self._uow:
            await self._event_publisher.publish(
                SubscriptionEditedEvent(
                    user=actor, action="delete_all_devices", subscription_id=subscription.id
                )
            )
        logger.info(f"{actor.log} Deleted all devices of subscription '{subscription.id}'")

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import DeleteUserHwidDeviceRequestDto

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import AdminDeleteDeviceDto
from app.modules.subscriptions.eligibility import get_live_subscription
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.repository import SubscriptionRepository


class AdminDeleteDeviceUseCase(UseCase[AdminDeleteDeviceDto, None]):
    required_permission = Permission.SUBSCRIPTIONS_DEVICES_DELETE

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

    async def _execute(self, actor: Actor, data: AdminDeleteDeviceDto) -> None:
        async with self._uow:
            subscription = await get_live_subscription(
                self._subscription_repository, data.subscription_id
            )
        await self._remnawave_sdk.hwid.delete_hwid_to_user(
            DeleteUserHwidDeviceRequestDto(user_id=subscription.remnawave_user_id, hwid=data.hwid)
        )
        async with self._uow:
            await self._event_publisher.publish(
                SubscriptionEditedEvent(
                    user=actor, action="delete_device", subscription_id=subscription.id
                )
            )
        logger.info(f"{actor.log} Deleted a device of subscription '{subscription.id}'")

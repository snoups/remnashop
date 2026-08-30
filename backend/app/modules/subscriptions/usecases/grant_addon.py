from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import UpdateUserRequestDto

from app.core.constants import GB_TO_BYTES
from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.dto import GrantAddOnDto, SubscriptionDto
from app.modules.subscriptions.events import SubscriptionAddOnGrantedEvent
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class GrantAddOnUseCase(UseCase[GrantAddOnDto, SubscriptionDto]):
    # System-invoked only, same shape as RegisterTelegramUserUseCase -- no
    # real actor ever grants an add-on to themselves directly; this always
    # runs .system()-bound from the future payment-confirmation task.
    required_permission = None

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        addon_repository: AddOnRepository,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._addon_repository = addon_repository
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: GrantAddOnDto) -> SubscriptionDto:
        addon = await self._addon_repository.get_by_id(data.addon_id)

        async with self._uow:
            subscription = await self._subscription_repository.grant_entitlement(
                subscription_id=data.subscription_id,
                addon_id=addon.id,
                addon_type=addon.type,
                amount=addon.amount,
            )

        if addon.type == AddOnType.TRAFFIC:
            request = UpdateUserRequestDto(
                id=subscription.remnawave_user_id,
                traffic_limit_bytes=subscription.effective_traffic_limit * GB_TO_BYTES,
            )
        else:
            request = UpdateUserRequestDto(
                id=subscription.remnawave_user_id,
                hwid_device_limit=subscription.effective_device_limit,
            )
        await self._remnawave_sdk.users.update_user(request)

        logger.info(
            f"Granted addon '{addon.id}' ({addon.amount} {addon.type.value}) "
            f"to subscription '{subscription.id}'"
        )
        await self._event_publisher.publish(
            SubscriptionAddOnGrantedEvent(
                user=actor,
                subscription_id=subscription.id,
                addon_id=addon.id,
                amount=addon.amount,
            )
        )
        return subscription

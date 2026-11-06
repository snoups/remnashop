from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import DeviceDto
from app.modules.subscriptions.eligibility import get_manageable_subscription
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserRepository


class AdminListDevicesUseCase(UseCase[int, list[DeviceDto]]):
    required_permission = Permission.SUBSCRIPTIONS_DEVICES_VIEW

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> list[DeviceDto]:
        async with self._uow:
            subscription = await get_manageable_subscription(
                self._subscription_repository, self._user_repository, actor, data, for_read=True
            )
        response = await self._remnawave_sdk.hwid.get_hwid_user(subscription.remnawave_user_id)
        return [
            DeviceDto.model_validate(device, from_attributes=True) for device in response.devices
        ]

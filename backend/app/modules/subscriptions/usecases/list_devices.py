from remnapy import RemnawaveSDK

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import DeviceDto, SubscriptionRefDto
from app.modules.subscriptions.eligibility import get_owned_live_target
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class ListDevicesUseCase(UseCase[SubscriptionRefDto, list[DeviceDto], UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow

    async def _execute(self, actor: UserDto, data: SubscriptionRefDto) -> list[DeviceDto]:
        async with self._uow:
            subscription = await get_owned_live_target(
                self._subscription_repository, data.subscription_id, actor.id
            )
        response = await self._remnawave_sdk.hwid.get_hwid_user(subscription.remnawave_user_id)
        return [
            DeviceDto.model_validate(device, from_attributes=True) for device in response.devices
        ]

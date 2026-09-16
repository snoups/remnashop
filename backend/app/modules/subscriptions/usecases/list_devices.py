from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from remnapy import RemnawaveSDK

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class DeviceDto(BaseModel):
    hwid: str
    platform: Optional[str]
    device_model: Optional[str]
    user_agent: Optional[str]
    created_at: datetime


class ListDevicesUseCase(UseCase[None, list[DeviceDto]]):
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

    async def _execute(self, actor: UserDto, data: None) -> list[DeviceDto]:
        async with self._uow:
            subscription = (
                await self._subscription_repository.get_single_active_subscription_or_raise(
                    actor.id
                )
            )
        response = await self._remnawave_sdk.hwid.get_hwid_user(subscription.remnawave_user_id)
        return [
            DeviceDto(
                hwid=device.hwid,
                platform=device.platform,
                device_model=device.device_model,
                user_agent=device.user_agent,
                created_at=device.created_at,
            )
            for device in response.devices
        ]

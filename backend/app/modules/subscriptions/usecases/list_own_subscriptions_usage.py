import asyncio
from typing import Optional

from loguru import logger
from remnapy import RemnawaveSDK

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import OwnSubscriptionUsageDto, SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class ListOwnSubscriptionsUsageUseCase(UseCase[None, list[OwnSubscriptionUsageDto], UserDto]):
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

    async def _execute(self, actor: UserDto, data: None) -> list[OwnSubscriptionUsageDto]:
        async with self._uow:
            subscriptions = await self._subscription_repository.get_active_by_user(actor.id)
        # the panel is queried outside the transaction so a slow panel can't hold a connection
        used = await asyncio.gather(*(self._used_traffic(s) for s in subscriptions))
        return [
            OwnSubscriptionUsageDto(subscription=s, used_traffic=u)
            for s, u in zip(subscriptions, used)
        ]

    async def _used_traffic(self, subscription: SubscriptionDto) -> Optional[int]:
        try:
            panel_user = await self._remnawave_sdk.users.get_user_by_id(
                subscription.remnawave_user_id
            )
        except Exception as e:
            logger.warning(
                "Panel usage lookup failed for subscription '{}': {}", subscription.id, e
            )
            return None
        return int(panel_user.used_traffic_bytes)  # the SDK types it as float

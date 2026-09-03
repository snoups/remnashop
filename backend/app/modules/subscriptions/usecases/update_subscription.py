from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import UpdateUserRequestDto

from app.core.constants import GB_TO_BYTES
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto, UpdateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class UpdateSubscriptionUseCase(UseCase[UpdateSubscriptionDto, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_UPDATE

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdateSubscriptionDto) -> SubscriptionDto:
        async with self._uow:
            subscription = await self._subscription_repository.update(data)

        if data.traffic_limit is not None or data.device_limit is not None:
            await self._remnawave_sdk.users.update_user(
                UpdateUserRequestDto(
                    id=subscription.remnawave_user_id,
                    traffic_limit_bytes=subscription.effective_traffic_limit * GB_TO_BYTES,
                    hwid_device_limit=subscription.effective_device_limit,
                )
            )

        logger.info(f"{actor.log} Updated subscription '{subscription.id}'")
        return subscription

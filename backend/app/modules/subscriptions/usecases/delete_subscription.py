from loguru import logger
from remnapy import RemnawaveSDK

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class DeleteSubscriptionUseCase(UseCase[int, None]):
    required_permission = Permission.SUBSCRIPTIONS_DELETE

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        async with self._uow:
            subscription = await self._subscription_repository.get_by_id(data)

        # Revoke the panel identity before the local row is marked deleted --
        # if the panel call fails, it propagates and the row stays visibly
        # active instead of silently claiming "deleted" while VPN access
        # still works.
        await self._remnawave_sdk.users.delete_user(subscription.remnawave_user_id)

        async with self._uow:
            await self._subscription_repository.mark_deleted(data)
        logger.info(f"{actor.log} Deleted subscription '{data}'")

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class DeleteSubscriptionUseCase(UseCase[int, None]):
    required_permission = Permission.SUBSCRIPTIONS_DELETE

    def __init__(self, subscription_repository: SubscriptionRepository, uow: UnitOfWork) -> None:
        self._subscription_repository = subscription_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        async with self._uow:
            await self._subscription_repository.mark_deleted(data)
        logger.info(f"{actor.log} Deleted subscription '{data}'")

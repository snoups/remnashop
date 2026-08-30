from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto, UpdateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class UpdateSubscriptionUseCase(UseCase[UpdateSubscriptionDto, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_UPDATE

    def __init__(self, subscription_repository: SubscriptionRepository, uow: UnitOfWork) -> None:
        self._subscription_repository = subscription_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdateSubscriptionDto) -> SubscriptionDto:
        async with self._uow:
            subscription = await self._subscription_repository.update(data)
        logger.info(f"{actor.log} Updated subscription '{subscription.id}'")
        return subscription

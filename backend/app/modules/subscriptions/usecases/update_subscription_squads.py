from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto, UpdateSubscriptionSquadsDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class UpdateSubscriptionSquadsUseCase(UseCase[UpdateSubscriptionSquadsDto, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_SQUADS_MANAGE

    def __init__(self, subscription_repository: SubscriptionRepository, uow: UnitOfWork) -> None:
        self._subscription_repository = subscription_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdateSubscriptionSquadsDto) -> SubscriptionDto:
        async with self._uow:
            subscription = await self._subscription_repository.update_squads(data)
        logger.info(f"{actor.log} Updated squads for subscription '{data.subscription_id}'")
        return subscription

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository


class GetSubscriptionUseCase(UseCase[int, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_DETAIL_VIEW

    def __init__(self, subscription_repository: SubscriptionRepository, uow: UnitOfWork) -> None:
        self._subscription_repository = subscription_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> SubscriptionDto:
        async with self._uow:
            return await self._subscription_repository.get_by_id(data)

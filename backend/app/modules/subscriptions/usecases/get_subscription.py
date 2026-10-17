from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.eligibility import get_visible_subscription
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserRepository


class GetSubscriptionUseCase(UseCase[int, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_DETAIL_VIEW

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> SubscriptionDto:
        async with self._uow:
            return await get_visible_subscription(
                self._subscription_repository, self._user_repository, actor, data
            )

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class ListOwnSubscriptionsUseCase(UseCase[None, list[SubscriptionDto], UserDto]):
    """Every subscription the customer can still renew or change, EXPIRED included."""

    required_permission = Permission.PUBLIC

    def __init__(self, subscription_repository: SubscriptionRepository, uow: UnitOfWork) -> None:
        self._subscription_repository = subscription_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> list[SubscriptionDto]:
        async with self._uow:
            return await self._subscription_repository.get_live_by_user(actor.id)

from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


class ListSubscriptionsUseCase(UseCase[None, list[SubscriptionDto]]):
    required_permission = Permission.SUBSCRIPTIONS_VIEW

    def __init__(self, subscription_repository: SubscriptionRepository) -> None:
        self._subscription_repository = subscription_repository

    async def _execute(self, actor: UserDto, data: None) -> list[SubscriptionDto]:
        return await self._subscription_repository.list_all()

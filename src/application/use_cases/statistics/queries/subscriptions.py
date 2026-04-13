from src.application.common import Interactor
from src.application.common.dao import SubscriptionDao
from src.application.common.policy import Permission
from src.application.dto import SubscriptionStatsDto, UserDto


class GetSubscriptionStatistics(Interactor[None, SubscriptionStatsDto]):
    required_permission = Permission.VIEW_STATISTICS

    def __init__(self, subscription_dao: SubscriptionDao) -> None:
        self.subscription_dao = subscription_dao

    async def _execute(self, actor: UserDto, data: None) -> SubscriptionStatsDto:
        return await self.subscription_dao.get_stats()

from dataclasses import dataclass

from src.application.common import Interactor, TranslatorRunner
from src.application.common.dao import SubscriptionDao, TransactionDao
from src.application.common.policy import Permission
from src.application.dto import PlanIncomeDto, PlanSubStatsDto, UserDto


@dataclass(frozen=True)
class PlansStatisticsDto:
    plans: list[PlanSubStatsDto]
    income: list[PlanIncomeDto]


class GetPlanStatistics(Interactor[None, PlansStatisticsDto]):
    required_permission = Permission.VIEW_STATISTICS

    def __init__(
        self,
        subscription_dao: SubscriptionDao,
        transaction_dao: TransactionDao,
        i18n: TranslatorRunner,
    ) -> None:
        self.subscription_dao = subscription_dao
        self.transaction_dao = transaction_dao
        self.i18n = i18n

    async def _execute(self, actor: UserDto, data: None) -> PlansStatisticsDto:
        plans = await self.subscription_dao.get_plan_sub_stats()
        income = await self.transaction_dao.get_plan_income()
        return PlansStatisticsDto(plans, income)

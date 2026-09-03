from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto, SetPlanDurationBasePriceDto
from app.modules.plans.repository import PlanRepository
from app.modules.users import UserDto


class SetPlanDurationBasePriceUseCase(UseCase[SetPlanDurationBasePriceDto, PlanDto]):
    required_permission = Permission.PLANS_DURATION_BASE_PRICE_MANAGE

    def __init__(self, plan_repository: PlanRepository, uow: UnitOfWork) -> None:
        self._plan_repository = plan_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: SetPlanDurationBasePriceDto) -> PlanDto:
        async with self._uow:
            plan = await self._plan_repository.set_duration_base_price(data)
        logger.info(f"{actor.log} Set base price for plan '{data.plan_id}' duration '{data.days}'")
        return plan

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto, UpdatePlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.users import UserDto


class UpdatePlanUseCase(UseCase[UpdatePlanDto, PlanDto]):
    required_permission = Permission.PLANS_UPDATE

    def __init__(self, plan_repository: PlanRepository, uow: UnitOfWork) -> None:
        self._plan_repository = plan_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdatePlanDto) -> PlanDto:
        async with self._uow:
            plan = await self._plan_repository.update(data)
        logger.info(f"{actor.log} Updated plan '{plan.id}'")
        return plan

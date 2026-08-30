from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto, UpdatePlanSquadsDto
from app.modules.plans.repository import PlanRepository
from app.modules.users import UserDto


class UpdatePlanSquadsUseCase(UseCase[UpdatePlanSquadsDto, PlanDto]):
    required_permission = Permission.PLANS_SQUADS_MANAGE

    def __init__(self, plan_repository: PlanRepository, uow: UnitOfWork) -> None:
        self._plan_repository = plan_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdatePlanSquadsDto) -> PlanDto:
        async with self._uow:
            plan = await self._plan_repository.update_squads(data)
        logger.info(f"{actor.log} Updated squads for plan '{data.plan_id}'")
        return plan

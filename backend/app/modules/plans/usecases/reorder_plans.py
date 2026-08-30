from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto, ReorderPlansDto
from app.modules.plans.repository import PlanRepository
from app.modules.users import UserDto


class ReorderPlansUseCase(UseCase[ReorderPlansDto, list[PlanDto]]):
    required_permission = Permission.PLANS_ORDER_MANAGE

    def __init__(self, plan_repository: PlanRepository, uow: UnitOfWork) -> None:
        self._plan_repository = plan_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: ReorderPlansDto) -> list[PlanDto]:
        async with self._uow:
            plans = await self._plan_repository.reorder(data)
        logger.info(f"{actor.log} Reordered plans")
        return plans

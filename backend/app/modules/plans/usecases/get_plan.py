from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto
from app.modules.plans.repository import PlanRepository


class GetPlanUseCase(UseCase[int, PlanDto]):
    required_permission = Permission.PLANS_DETAIL_VIEW

    def __init__(self, plan_repository: PlanRepository, uow: UnitOfWork) -> None:
        self._plan_repository = plan_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> PlanDto:
        async with self._uow:
            return await self._plan_repository.get_by_id(data)

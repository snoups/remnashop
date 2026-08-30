from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.users import UserDto


class ListPlansUseCase(UseCase[None, list[PlanDto]]):
    required_permission = Permission.PLANS_VIEW

    def __init__(self, plan_repository: PlanRepository) -> None:
        self._plan_repository = plan_repository

    async def _execute(self, actor: UserDto, data: None) -> list[PlanDto]:
        return await self._plan_repository.list_all()

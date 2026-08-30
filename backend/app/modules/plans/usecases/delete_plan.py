from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.repository import PlanRepository
from app.modules.users import UserDto


class DeletePlanUseCase(UseCase[int, None]):
    required_permission = Permission.PLANS_DELETE

    def __init__(self, plan_repository: PlanRepository, uow: UnitOfWork) -> None:
        self._plan_repository = plan_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        async with self._uow:
            await self._plan_repository.delete(data)
        logger.info(f"{actor.log} Deleted plan '{data}'")

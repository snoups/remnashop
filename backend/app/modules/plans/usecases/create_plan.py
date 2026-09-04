from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import CreatePlanDto, PlanDto
from app.modules.plans.events import PlanChangedEvent
from app.modules.plans.repository import PlanRepository
from app.modules.users import UserDto


class CreatePlanUseCase(UseCase[CreatePlanDto, PlanDto]):
    required_permission = Permission.PLANS_CREATE

    def __init__(
        self, plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._plan_repository = plan_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: CreatePlanDto) -> PlanDto:
        async with self._uow:
            plan = await self._plan_repository.create(data)
            await self._event_publisher.publish(
                PlanChangedEvent(user=actor, action="create", plan_id=plan.id)
            )
        logger.info(f"{actor.log} Created plan '{plan.name}'")
        return plan

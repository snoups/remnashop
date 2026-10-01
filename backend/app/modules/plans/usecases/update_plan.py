from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto, UpdatePlanDto
from app.modules.plans.events import PlanChangedEvent
from app.modules.plans.repository import PlanRepository


class UpdatePlanUseCase(UseCase[UpdatePlanDto, PlanDto]):
    required_permission = Permission.PLANS_UPDATE

    def __init__(
        self, plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._plan_repository = plan_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdatePlanDto) -> PlanDto:
        async with self._uow:
            plan = await self._plan_repository.update(data)
            await self._event_publisher.publish(
                PlanChangedEvent(user=actor, action="update", plan_id=plan.id)
            )
        logger.info(f"{actor.log} Updated plan '{plan.id}'")
        return plan

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto, UpdatePlanAccessDto
from app.modules.plans.events import PlanChangedEvent
from app.modules.plans.repository import PlanRepository


class UpdatePlanAccessUseCase(UseCase[UpdatePlanAccessDto, PlanDto]):
    required_permission = Permission.PLANS_ACCESS_MANAGE

    def __init__(
        self, plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._plan_repository = plan_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdatePlanAccessDto) -> PlanDto:
        async with self._uow:
            plan = await self._plan_repository.update_access(data)
            await self._event_publisher.publish(
                PlanChangedEvent(actor=actor, action="access", plan_id=data.plan_id)
            )
        logger.info(f"{actor.log} Updated access for plan '{data.plan_id}'")
        return plan

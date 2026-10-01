from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.events import PlanChangedEvent
from app.modules.plans.repository import PlanRepository


class DeletePlanUseCase(UseCase[int, None]):
    required_permission = Permission.PLANS_DELETE

    def __init__(
        self, plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._plan_repository = plan_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            await self._plan_repository.delete(data)
            await self._event_publisher.publish(
                PlanChangedEvent(user=actor, action="delete", plan_id=data)
            )
        logger.info(f"{actor.log} Deleted plan '{data}'")

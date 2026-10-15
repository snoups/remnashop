from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto, ReorderPlansDto
from app.modules.plans.events import PlanChangedEvent
from app.modules.plans.repository import PlanRepository


class ReorderPlansUseCase(UseCase[ReorderPlansDto, list[PlanDto]]):
    required_permission = Permission.PLANS_ORDER_MANAGE

    def __init__(
        self, plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._plan_repository = plan_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: ReorderPlansDto) -> list[PlanDto]:
        async with self._uow:
            plans = await self._plan_repository.reorder(data)
            await self._event_publisher.publish(PlanChangedEvent(actor=actor, action="reorder"))
        logger.info(f"{actor.log} Reordered plans")
        return plans

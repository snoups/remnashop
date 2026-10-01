from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto, SetPlanDurationBasePriceDto
from app.modules.plans.events import PlanChangedEvent
from app.modules.plans.repository import PlanRepository


class SetPlanDurationBasePriceUseCase(UseCase[SetPlanDurationBasePriceDto, PlanDto]):
    required_permission = Permission.PLANS_DURATION_BASE_PRICE_MANAGE

    def __init__(
        self, plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._plan_repository = plan_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: SetPlanDurationBasePriceDto) -> PlanDto:
        async with self._uow:
            plan = await self._plan_repository.set_duration_base_price(data)
            await self._event_publisher.publish(
                PlanChangedEvent(user=actor, action="base_price", plan_id=data.plan_id)
            )
        logger.info(f"{actor.log} Set base price for plan '{data.plan_id}' duration '{data.days}'")
        return plan

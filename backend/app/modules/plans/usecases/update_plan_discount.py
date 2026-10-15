from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto, UpdatePlanDiscountDto
from app.modules.plans.events import PlanChangedEvent
from app.modules.plans.repository import PlanRepository


class UpdatePlanDiscountUseCase(UseCase[UpdatePlanDiscountDto, PlanDto]):
    required_permission = Permission.PLANS_DISCOUNT_MANAGE

    def __init__(
        self, plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._plan_repository = plan_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdatePlanDiscountDto) -> PlanDto:
        starts_at, ends_at = data.discount_starts_at, data.discount_ends_at
        if starts_at is not None and ends_at is not None and starts_at >= ends_at:
            raise ValidationError(
                "The discount must start before it ends",
                code=ErrorCode.PLAN_DISCOUNT_WINDOW_INVALID,
            )

        async with self._uow:
            plan = await self._plan_repository.update_discount(data)
            await self._event_publisher.publish(
                PlanChangedEvent(actor=actor, action="discount", plan_id=data.plan_id)
            )
        logger.info(f"{actor.log} Set a {data.discount_percent}% discount on plan '{data.plan_id}'")
        return plan

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto, SetPlanDurationsDto
from app.modules.plans.events import PlanChangedEvent
from app.modules.plans.repository import PlanRepository


class SetPlanDurationsUseCase(UseCase[SetPlanDurationsDto, PlanDto]):
    required_permission = Permission.PLANS_DURATIONS_MANAGE

    def __init__(
        self, plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._plan_repository = plan_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: SetPlanDurationsDto) -> PlanDto:
        async with self._uow:
            current = await self._plan_repository.get_by_id(data.plan_id)
            if current.is_trial and len(data.durations) > 1:
                raise ValidationError(
                    "A trial plan has exactly one duration",
                    code=ErrorCode.PLAN_TRIAL_SINGLE_DURATION,
                )
            if not current.is_trial and any(d.base_price == 0 for d in data.durations):
                raise ValidationError(
                    "Only a trial plan can have a free duration",
                    code=ErrorCode.PLAN_DURATION_PRICE_REQUIRED,
                )
            plan = await self._plan_repository.set_durations(data)
            await self._event_publisher.publish(
                PlanChangedEvent(actor=actor, action="durations", plan_id=data.plan_id)
            )
        logger.info(f"{actor.log} Set durations for plan '{data.plan_id}'")
        return plan

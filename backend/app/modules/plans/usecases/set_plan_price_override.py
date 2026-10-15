from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.dto import PlanDto, SetPlanPriceOverrideDto
from app.modules.plans.events import PlanChangedEvent
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import PricingRepository, assert_overridable_currency


class SetPlanPriceOverrideUseCase(UseCase[SetPlanPriceOverrideDto, PlanDto]):
    required_permission = Permission.PLANS_PRICE_OVERRIDE_MANAGE

    def __init__(
        self,
        plan_repository: PlanRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._plan_repository = plan_repository
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: SetPlanPriceOverrideDto) -> PlanDto:
        async with self._uow:
            if data.price is not None:  # clearing stays allowed, e.g. after an anchor switch
                settings = await self._pricing_repository.get_settings()
                assert_overridable_currency(data.currency, settings.anchor_currency)
            plan = await self._plan_repository.set_price_override(data)
            await self._event_publisher.publish(
                PlanChangedEvent(actor=actor, action="price_override", plan_id=data.plan_id)
            )
        logger.info(
            f"{actor.log} Set price override for plan '{data.plan_id}' "
            f"duration '{data.days}' currency '{data.currency}'"
        )
        return plan

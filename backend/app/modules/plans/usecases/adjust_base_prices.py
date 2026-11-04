from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PriceAdjustMode
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import AdjustBasePricesDto, PriceBookDto
from app.modules.plans.price_book import build_price_book
from app.modules.plans.price_projection import adjusted_base_prices
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import (
    BasePricesAdjustedEvent,
    PricingRepository,
)


class AdjustBasePricesUseCase(UseCase[AdjustBasePricesDto, PriceBookDto]):
    required_permission = Permission.PRICING_BASE_ADJUST_MANAGE

    def __init__(
        self,
        plan_repository: PlanRepository,
        addon_repository: AddOnRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._plan_repository = plan_repository
        self._addon_repository = addon_repository
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: AdjustBasePricesDto) -> PriceBookDto:
        async with self._uow:
            adjustment = adjusted_base_prices(
                data,
                await self._plan_repository.list_all(),
                await self._addon_repository.list_all(),
                await self._pricing_repository.get_rate_table(),
            )
            if adjustment.plan_prices:
                await self._plan_repository.set_duration_base_prices(adjustment.plan_prices)
            if adjustment.plan_overrides:
                await self._plan_repository.replace_duration_overrides(adjustment.plan_overrides)
            if adjustment.addon_prices:
                await self._addon_repository.set_base_prices(adjustment.addon_prices)
            if adjustment.addon_overrides:
                await self._addon_repository.replace_overrides(adjustment.addon_overrides)
            await self._event_publisher.publish(
                BasePricesAdjustedEvent(
                    actor=actor,
                    scope=data.scope,
                    mode=data.mode,
                    value=str(data.factor if data.mode is PriceAdjustMode.MULTIPLY else data.price),
                    pinned=data.pinned,
                )
            )

        logger.info(f"{actor.log} Adjusted base prices for scope '{data.scope}'")
        async with self._uow:
            return await build_price_book(
                self._plan_repository, self._addon_repository, self._pricing_repository
            )

from decimal import Decimal

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PriceAdjustScope
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import AdjustBasePricesDto, PriceBookDto
from app.modules.plans.price_book import build_price_book
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import (
    BasePricesAdjustedEvent,
    PricingRepository,
    scale_base_price,
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
            if data.scope in (PriceAdjustScope.ALL_PLANS, PriceAdjustScope.SELECTED):
                plan_updates = await self._resolve_plan_updates(data)
                if plan_updates:
                    await self._plan_repository.set_duration_base_prices(plan_updates)

            if data.scope in (PriceAdjustScope.ALL_ADDONS, PriceAdjustScope.SELECTED):
                addon_updates = await self._resolve_addon_updates(data)
                if addon_updates:
                    await self._addon_repository.set_base_prices(addon_updates)

            await self._event_publisher.publish(
                BasePricesAdjustedEvent(actor=actor, scope=data.scope, factor=str(data.factor))
            )

        logger.info(f"{actor.log} Adjusted base prices for scope '{data.scope}'")
        async with self._uow:
            return await build_price_book(
                self._plan_repository, self._addon_repository, self._pricing_repository
            )

    async def _resolve_plan_updates(self, data: AdjustBasePricesDto) -> dict[int, Decimal]:
        plans = await self._plan_repository.list_all()
        durations = [duration for plan in plans for duration in plan.durations]
        if data.scope is PriceAdjustScope.SELECTED:
            selected_ids = set(data.plan_duration_ids)
            durations = [duration for duration in durations if duration.id in selected_ids]
        return {
            duration.id: scale_base_price(duration.base_price, data.factor)
            for duration in durations
        }

    async def _resolve_addon_updates(self, data: AdjustBasePricesDto) -> dict[int, Decimal]:
        addons = await self._addon_repository.list_all()
        if data.scope is PriceAdjustScope.SELECTED:
            selected_ids = set(data.addon_ids)
            addons = [addon for addon in addons if addon.id in selected_ids]
        return {addon.id: scale_base_price(addon.base_price, data.factor) for addon in addons}

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import PriceBookDto, SwitchAnchorCurrencyDto
from app.modules.plans.ports import AnchorAmountRescaler, LoyaltyThresholdRescaler
from app.modules.plans.price_book import build_price_book
from app.modules.plans.price_projection import anchor_switch, scale_unit_price
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import (
    NON_ANCHOR_CURRENCIES,
    AnchorSwitchedEvent,
    PricingRepository,
    UpdatePricingSettingsDto,
)


class SwitchAnchorCurrencyUseCase(UseCase[SwitchAnchorCurrencyDto, PriceBookDto]):
    required_permission = Permission.PRICING_ANCHOR_MANAGE

    def __init__(
        self,
        pricing_repository: PricingRepository,
        plan_repository: PlanRepository,
        addon_repository: AddOnRepository,
        anchor_amount_rescaler: AnchorAmountRescaler,
        loyalty_threshold_rescaler: LoyaltyThresholdRescaler,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._pricing_repository = pricing_repository
        self._plan_repository = plan_repository
        self._addon_repository = addon_repository
        self._anchor_amount_rescaler = anchor_amount_rescaler
        self._loyalty_threshold_rescaler = loyalty_threshold_rescaler
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: SwitchAnchorCurrencyDto) -> PriceBookDto:
        if data.new_anchor in NON_ANCHOR_CURRENCIES:
            raise ValidationError(
                f"{data.new_anchor} cannot be the anchor currency",
                code=ErrorCode.ANCHOR_CURRENCY_INVALID,
            )

        async with self._uow:
            await self._pricing_repository.lock_settings()
            table = await self._pricing_repository.get_rate_table()
            old_anchor = table.anchor
            if data.new_anchor == old_anchor:
                raise ValidationError(
                    "That currency is already the anchor", code=ErrorCode.ANCHOR_CURRENCY_UNCHANGED
                )

            plans = await self._plan_repository.list_all()
            addons = await self._addon_repository.list_all()
            switch = anchor_switch(table, data.new_anchor, plans, addons)

            await self._pricing_repository.set_anchor(data.new_anchor, switch.rates)
            await self._anchor_amount_rescaler.rescale_anchor_amounts(switch.factor)
            await self._loyalty_threshold_rescaler.rescale_thresholds(switch.factor)
            if switch.plan_base_prices:
                await self._plan_repository.set_duration_base_prices(switch.plan_base_prices)
            if switch.addon_base_prices:
                await self._addon_repository.set_base_prices(switch.addon_base_prices)

            settings = await self._pricing_repository.get_settings()
            await self._pricing_repository.update_settings(
                UpdatePricingSettingsDto(
                    price_per_day=scale_unit_price(settings.price_per_day, switch.factor),
                    price_per_gb=scale_unit_price(settings.price_per_gb, switch.factor),
                )
            )
            await self._event_publisher.publish(
                AnchorSwitchedEvent(actor=actor, old_anchor=old_anchor, new_anchor=data.new_anchor)
            )

        logger.info(f"{actor.log} Switched pricing anchor to '{data.new_anchor}'")
        async with self._uow:
            return await build_price_book(
                self._plan_repository, self._addon_repository, self._pricing_repository
            )

from decimal import Decimal

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanRepository
from app.modules.pricing.dto import (
    BASE_PRICE_PRECISION,
    MIN_BASE_PRICE,
    RATE_PRECISION,
    PriceBookDto,
    SwitchAnchorCurrencyDto,
    UpdatePricingSettingsDto,
)
from app.modules.pricing.events import AnchorSwitchedEvent
from app.modules.pricing.repository import PricingRepository
from app.modules.pricing.usecases.get_price_book import build_price_book
from app.modules.subscriptions import AddOnRepository
from app.modules.users import UserDto


class SwitchAnchorCurrencyUseCase(UseCase[SwitchAnchorCurrencyDto, PriceBookDto]):
    required_permission = Permission.PRICING_ANCHOR_MANAGE

    def __init__(
        self,
        pricing_repository: PricingRepository,
        plan_repository: PlanRepository,
        addon_repository: AddOnRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._pricing_repository = pricing_repository
        self._plan_repository = plan_repository
        self._addon_repository = addon_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: SwitchAnchorCurrencyDto) -> PriceBookDto:
        table = await self._pricing_repository.get_rate_table()
        old_anchor = table.anchor
        if data.new_anchor == old_anchor:
            raise ValidationError("That currency is already the anchor")

        f = table.rows[data.new_anchor].rate
        new_rates = {
            currency: (row.rate / f).quantize(RATE_PRECISION)
            for currency, row in table.rows.items()
        }
        new_rates[data.new_anchor] = Decimal("1.000000")

        async with self._uow:
            await self._pricing_repository.set_anchor(data.new_anchor, new_rates)

            plans = await self._plan_repository.list_all()
            plan_updates = {
                duration.id: max(
                    (duration.base_price * f).quantize(BASE_PRICE_PRECISION), MIN_BASE_PRICE
                )
                for plan in plans
                for duration in plan.durations
            }
            if plan_updates:
                await self._plan_repository.set_duration_base_prices(plan_updates)

            addons = await self._addon_repository.list_all()
            addon_updates = {
                addon.id: max((addon.base_price * f).quantize(BASE_PRICE_PRECISION), MIN_BASE_PRICE)
                for addon in addons
            }
            if addon_updates:
                await self._addon_repository.set_base_prices(addon_updates)

            settings = await self._pricing_repository.get_settings()
            await self._pricing_repository.update_settings(
                UpdatePricingSettingsDto(
                    price_per_day=(
                        (settings.price_per_day * f).quantize(BASE_PRICE_PRECISION)
                        if settings.price_per_day is not None
                        else None
                    ),
                    price_per_gb=(
                        (settings.price_per_gb * f).quantize(BASE_PRICE_PRECISION)
                        if settings.price_per_gb is not None
                        else None
                    ),
                )
            )
            await self._event_publisher.publish(
                AnchorSwitchedEvent(user=actor, old_anchor=old_anchor, new_anchor=data.new_anchor)
            )

        logger.info(f"{actor.log} Switched pricing anchor to '{data.new_anchor}'")
        return await build_price_book(
            self._plan_repository, self._addon_repository, self._pricing_repository
        )

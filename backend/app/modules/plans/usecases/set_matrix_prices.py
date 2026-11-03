from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.exceptions import PermissionDeniedError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import PriceBookDto, SetMatrixPricesDto
from app.modules.plans.events import AddOnChangedEvent, PlanChangedEvent
from app.modules.plans.price_book import build_price_book
from app.modules.plans.repository import PlanRepository
from app.modules.pricing import PricingRepository, assert_overridable_currency


class SetMatrixPricesUseCase(UseCase[SetMatrixPricesDto, PriceBookDto]):
    """Every edit of the price matrix in one transaction: all of them land, or none."""

    # each kind of edit below still needs its own permission
    required_permission = Permission.PRICING_MATRIX_MANAGE

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

    async def _execute(self, actor: Actor, data: SetMatrixPricesDto) -> PriceBookDto:
        self._check_edit_permissions(actor, data)

        async with self._uow:
            # an anchor switch rescales every base price under this lock
            await self._pricing_repository.lock_settings()
            settings = await self._pricing_repository.get_settings()
            # clearing stays allowed, e.g. after an anchor switch
            pinned = [
                *(item.currency for item in data.plan_overrides if item.price is not None),
                *(item.currency for item in data.addon_overrides if item.price is not None),
            ]
            for currency in pinned:
                assert_overridable_currency(currency, settings.anchor_currency)

            await self._apply(data)
            await self._publish(actor, data)

        logger.info(f"{actor.log} Set matrix prices")
        async with self._uow:
            return await build_price_book(
                self._plan_repository, self._addon_repository, self._pricing_repository
            )

    def _check_edit_permissions(self, actor: Actor, data: SetMatrixPricesDto) -> None:
        needed = (
            (data.plan_base_prices, Permission.PLANS_DURATION_BASE_PRICE_MANAGE),
            (data.plan_overrides, Permission.PLANS_PRICE_OVERRIDE_MANAGE),
            (data.addon_base_prices, Permission.ADDONS_PRICES_MANAGE),
            (data.addon_overrides, Permission.ADDONS_PRICE_OVERRIDE_MANAGE),
        )
        for edits, permission in needed:
            if edits and not PermissionPolicy.has_permission(actor, permission):
                logger.warning(f"Permission denied for actor {actor.log}")
                raise PermissionDeniedError

    async def _apply(self, data: SetMatrixPricesDto) -> None:
        for plan_price in data.plan_base_prices:
            await self._plan_repository.set_duration_base_price(plan_price)
        for plan_override in data.plan_overrides:
            await self._plan_repository.set_price_override(plan_override)
        for addon_price in data.addon_base_prices:
            await self._addon_repository.set_base_price(addon_price)
        for addon_override in data.addon_overrides:
            await self._addon_repository.set_price_override(addon_override)

    async def _publish(self, actor: Actor, data: SetMatrixPricesDto) -> None:
        for plan_id in sorted({edit.plan_id for edit in data.plan_base_prices}):
            await self._event_publisher.publish(
                PlanChangedEvent(actor=actor, action="base_price", plan_id=plan_id)
            )
        for plan_id in sorted({edit.plan_id for edit in data.plan_overrides}):
            await self._event_publisher.publish(
                PlanChangedEvent(actor=actor, action="price_override", plan_id=plan_id)
            )
        for addon_id in sorted({edit.addon_id for edit in data.addon_base_prices}):
            await self._event_publisher.publish(
                AddOnChangedEvent(actor=actor, action="base_price", addon_id=addon_id)
            )
        for addon_id in sorted({edit.addon_id for edit in data.addon_overrides}):
            await self._event_publisher.publish(
                AddOnChangedEvent(actor=actor, action="price_override", addon_id=addon_id)
            )

from dataclasses import replace
from functools import partial

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.loyalty.dispatch import LoyaltyRecalcDispatch
from app.modules.loyalty.dto import LoyaltySettingsDto, UpdateLoyaltySettingsDto
from app.modules.loyalty.events import LoyaltySettingsChangedEvent
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.tiers import validate_tiers
from app.modules.pricing import PricingRepository


class UpdateLoyaltySettingsUseCase(UseCase[UpdateLoyaltySettingsDto, LoyaltySettingsDto]):
    required_permission = Permission.LOYALTY_SETTINGS_MANAGE

    def __init__(
        self,
        loyalty_repository: LoyaltyRepository,
        pricing_repository: PricingRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
        recalc_dispatch: LoyaltyRecalcDispatch,
    ) -> None:
        self._loyalty_repository = loyalty_repository
        self._pricing_repository = pricing_repository
        self._event_publisher = event_publisher
        self._uow = uow
        self._recalc_dispatch = recalc_dispatch

    async def _execute(self, actor: Actor, data: UpdateLoyaltySettingsDto) -> LoyaltySettingsDto:
        validate_tiers(data.tiers, data.window_months)
        async with self._uow:
            saved = await self._loyalty_repository.save_settings(data)
            await self._event_publisher.publish(
                LoyaltySettingsChangedEvent(actor=actor, action="update")
            )
            await self._uow.after_commit(partial(self._recalc_dispatch.kiq, user_ids=None))
            pricing = await self._pricing_repository.get_settings()
        logger.info(f"{actor.log} Updated loyalty settings")
        return replace(saved, anchor_currency=pricing.anchor_currency)

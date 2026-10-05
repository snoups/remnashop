from dataclasses import replace

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.loyalty.dto import LoyaltySettingsDto
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.pricing import PricingRepository


class GetLoyaltySettingsUseCase(UseCase[None, LoyaltySettingsDto]):
    required_permission = Permission.LOYALTY_SETTINGS_VIEW

    def __init__(
        self,
        loyalty_repository: LoyaltyRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._loyalty_repository = loyalty_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> LoyaltySettingsDto:
        async with self._uow:
            settings = await self._loyalty_repository.get_settings()
            pricing = await self._pricing_repository.get_settings()
        return replace(settings, anchor_currency=pricing.anchor_currency)

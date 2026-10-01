from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.pricing import PricingRepository
from app.modules.referrals.dto import ReferralSettingsDto
from app.modules.referrals.repository import ReferralRepository


class GetReferralSettingsUseCase(UseCase[None, ReferralSettingsDto]):
    required_permission = Permission.REFERRALS_SETTINGS_VIEW

    def __init__(
        self,
        referral_repository: ReferralRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._referral_repository = referral_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> ReferralSettingsDto:
        async with self._uow:
            settings = await self._referral_repository.get_settings()
            pricing = await self._pricing_repository.get_settings()
        return settings.model_copy(update={"anchor_currency": pricing.anchor_currency})

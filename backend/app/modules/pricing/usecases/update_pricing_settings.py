from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.pricing.dto import PricingSettingsDto, UpdatePricingSettingsDto
from app.modules.pricing.repository import PricingRepository
from app.modules.users import UserDto


class UpdatePricingSettingsUseCase(UseCase[UpdatePricingSettingsDto, PricingSettingsDto]):
    required_permission = Permission.PRICING_SETTINGS_MANAGE

    def __init__(self, pricing_repository: PricingRepository, uow: UnitOfWork) -> None:
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdatePricingSettingsDto) -> PricingSettingsDto:
        async with self._uow:
            settings = await self._pricing_repository.update_settings(data)
        logger.info(f"{actor.log} Updated pricing settings")
        return settings

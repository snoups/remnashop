from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import ShopSettingsDto, UpdateShopSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


class UpdateShopSettingsUseCase(UseCase[UpdateShopSettingsDto, ShopSettingsDto]):
    required_permission = Permission.SHOP_SETTINGS_MANAGE

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdateShopSettingsDto) -> ShopSettingsDto:
        if data.max_active_subscriptions is not None and data.max_active_subscriptions < 1:
            raise ValidationError(
                "max_active_subscriptions must be positive, or null for unlimited"
            )

        async with self._uow:
            settings = await self._settings_repository.update_shop_settings(data)
        logger.info(f"Shop settings updated by actor {actor.log}")
        return settings

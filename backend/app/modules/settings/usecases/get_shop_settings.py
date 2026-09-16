from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import ShopSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


class GetShopSettingsUseCase(UseCase[None, ShopSettingsDto]):
    required_permission = Permission.SHOP_SETTINGS_VIEW

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> ShopSettingsDto:
        async with self._uow:
            return await self._settings_repository.get_shop_settings()

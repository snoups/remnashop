from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import CabinetSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.telegram_status import fetch_bot_username
from app.modules.users import UserDto


class GetCabinetSettingsUseCase(UseCase[None, CabinetSettingsDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> CabinetSettingsDto:
        async with self._uow:
            shop = await self._settings_repository.get_shop_settings()
            bot = await self._settings_repository.get_bot_settings()

        # outside the transaction: the network call must not hold a connection
        username: Optional[str] = None
        if bot.is_configured and bot.token is not None:
            username = await fetch_bot_username(bot.token.get_secret_value(), bot.proxy)
        return CabinetSettingsDto(
            max_active_subscriptions=shop.max_active_subscriptions,
            device_single_reset_enabled=shop.device_single_reset_enabled,
            device_all_reset_enabled=shop.device_all_reset_enabled,
            link_reset_enabled=shop.link_reset_enabled,
            bot_username=username,
            support_telegram=shop.support_telegram,
            support_url=shop.support_url,
        )

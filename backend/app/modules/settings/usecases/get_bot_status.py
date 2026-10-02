from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import BotStatusDto
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.telegram_status import fetch_bot_status


class GetBotStatusUseCase(UseCase[None, BotStatusDto]):
    required_permission = Permission.BOT_STATUS_VIEW

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> BotStatusDto:
        async with self._uow:
            settings = await self._settings_repository.get_bot_settings()
        if not settings.is_configured or settings.token is None:
            return BotStatusDto(is_configured=False)
        return await fetch_bot_status(settings.token.get_secret_value(), settings.proxy)

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import BotSettingsDto
from app.modules.settings.events import BotSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository


class RemoveBotProxyUseCase(UseCase[None, BotSettingsDto]):
    required_permission = Permission.BOT_PROXY_REMOVE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> BotSettingsDto:
        async with self._uow:
            settings = await self._settings_repository.set_bot_proxy_url(None)
            await self._event_publisher.publish(
                BotSettingsChangedEvent(actor=actor, action="proxy_remove")
            )
        logger.info(f"{actor.log} Removed the bot proxy")
        return settings

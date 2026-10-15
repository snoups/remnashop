from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.events import changed_fields
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import BotSettingsDto, UpdateBotSettingsDto
from app.modules.settings.events import BotSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository


class UpdateBotSettingsUseCase(UseCase[UpdateBotSettingsDto, BotSettingsDto]):
    required_permission = Permission.BOT_SETTINGS_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdateBotSettingsDto) -> BotSettingsDto:
        async with self._uow:
            before = await self._settings_repository.get_bot_settings()
            settings = await self._settings_repository.update_bot_settings(data)
            await self._event_publisher.publish(
                BotSettingsChangedEvent(
                    actor=actor,
                    action="update",
                    changed_fields=changed_fields(before, settings, vars(data)),
                )
            )
        logger.info(f"{actor.log} Updated bot settings")
        return settings

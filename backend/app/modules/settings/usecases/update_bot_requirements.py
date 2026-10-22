from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.events import changed_fields
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import BotRequirementsDto, UpdateBotRequirementsDto
from app.modules.settings.events import BotRequirementsChangedEvent
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.telegram_status import is_bot_channel_admin


class UpdateBotRequirementsUseCase(UseCase[UpdateBotRequirementsDto, BotRequirementsDto]):
    required_permission = Permission.BOT_REQUIREMENTS_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdateBotRequirementsDto) -> BotRequirementsDto:
        if data.channel_required:
            if data.channel_id is None or not data.channel_url:
                raise ValidationError(
                    "Channel id and URL are required", code=ErrorCode.BOT_REQUIREMENTS_INCOMPLETE
                )
            await self._assert_channel_accessible(data.channel_id)

        async with self._uow:
            before = await self._settings_repository.get_bot_requirements()
            settings = await self._settings_repository.update_bot_requirements(data)
            await self._event_publisher.publish(
                BotRequirementsChangedEvent(
                    actor=actor, changed_fields=changed_fields(before, settings, vars(data))
                )
            )
        logger.info(f"{actor.log} Updated bot requirements")
        return settings

    async def _assert_channel_accessible(self, channel_id: int) -> None:
        async with self._uow:
            bot = await self._settings_repository.get_bot_settings()
        if bot.token is None or not await is_bot_channel_admin(
            bot.token.get_secret_value(), bot.proxy, channel_id
        ):
            raise ValidationError(
                "The bot is not an admin of this channel", code=ErrorCode.CHANNEL_NOT_ACCESSIBLE
            )

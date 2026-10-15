from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import BotCommandsSync, EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.bot_commands import BOT_COMMANDS
from app.modules.settings.dto import UpdateBotCommandsDto, UpdateBotCommandsResultDto
from app.modules.settings.events import BotSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository


class UpdateBotCommandsUseCase(UseCase[UpdateBotCommandsDto, UpdateBotCommandsResultDto]):
    required_permission = Permission.BOT_COMMANDS_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        bot_commands: BotCommandsSync,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._bot_commands = bot_commands
        self._event_publisher = event_publisher

    async def _execute(
        self, actor: Actor, data: UpdateBotCommandsDto
    ) -> UpdateBotCommandsResultDto:
        current_names = {item.command for item in BOT_COMMANDS}
        submitted_names = {command for command, _ in data.commands}
        if submitted_names != current_names:
            raise ValidationError(
                f"Commands must match the current set exactly: expected {sorted(current_names)}, "
                f"got {sorted(submitted_names)}",
                code=ErrorCode.BOT_COMMANDS_MISMATCH,
            )

        async with self._uow:
            commands = await self._settings_repository.replace_bot_commands(data.commands)
            await self._event_publisher.publish(
                BotSettingsChangedEvent(actor=actor, action="commands")
            )
        return UpdateBotCommandsResultDto(
            commands=commands, telegram_sync_failed=not await self._bot_commands.push()
        )

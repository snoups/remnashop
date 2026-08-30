from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.bot_commands import BOT_COMMANDS
from app.modules.settings.dto import BotCommandDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


class GetBotCommandsUseCase(UseCase[None, list[BotCommandDto]]):
    required_permission = Permission.BOT_COMMANDS_VIEW

    def __init__(self, settings_repository: SettingsRepository) -> None:
        self._settings_repository = settings_repository

    async def _execute(self, actor: UserDto, data: None) -> list[BotCommandDto]:
        rows = await self._settings_repository.list_bot_commands()
        stored = {item.command: item for item in rows}

        merged = [
            stored[current.command]
            if current.command in stored
            else BotCommandDto(command=current.command, sort_order=index, enabled=True)
            for index, current in enumerate(BOT_COMMANDS)
        ]
        merged.sort(key=lambda item: item.sort_order)
        return merged

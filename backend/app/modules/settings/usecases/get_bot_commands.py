from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.bot_commands import BOT_COMMANDS
from app.modules.settings.dto import BotCommandDto
from app.modules.settings.repository import SettingsRepository


class GetBotCommandsUseCase(UseCase[bool, list[BotCommandDto]]):
    required_permission = Permission.BOT_COMMANDS_VIEW

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    # data is the reset-order flag: True hands back BOT_COMMANDS' own order
    # instead of the stored one, for the dashboard's "reset order" button.
    async def _execute(self, actor: Actor, data: bool) -> list[BotCommandDto]:
        async with self._uow:
            rows = await self._settings_repository.list_bot_commands()
            stored = {item.command: item for item in rows}

            merged = [
                stored[current.command]
                if current.command in stored
                else BotCommandDto(command=current.command, sort_order=index, enabled=True)
                for index, current in enumerate(BOT_COMMANDS)
            ]
            if not data:
                merged.sort(key=lambda item: item.sort_order)
            return merged

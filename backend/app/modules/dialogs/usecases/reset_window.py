from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import BotSignals
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs.dto import DialogWindowDto
from app.modules.dialogs.repository import DialogRepository


class ResetDialogWindowUseCase(UseCase[str, DialogWindowDto]):
    required_permission = Permission.DIALOGS_WINDOWS_RESET

    def __init__(
        self, dialog_repository: DialogRepository, uow: UnitOfWork, bot_signals: BotSignals
    ) -> None:
        self._dialog_repository = dialog_repository
        self._uow = uow
        self._bot_signals = bot_signals

    async def _execute(self, actor: Actor, data: str) -> DialogWindowDto:
        async with self._uow:
            window = await self._dialog_repository.reset_to_snapshot(data)
        await self._bot_signals.dialogs_changed()
        return window

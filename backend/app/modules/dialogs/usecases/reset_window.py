from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs.dto import DialogWindowDto
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._publish import publish_dialog_change


class ResetDialogWindowUseCase(UseCase[str, DialogWindowDto]):
    required_permission = Permission.DIALOGS_WINDOWS_RESET

    def __init__(self, dialog_repository: DialogRepository, uow: UnitOfWork, redis: Redis) -> None:
        self._dialog_repository = dialog_repository
        self._uow = uow
        self._redis = redis

    async def _execute(self, actor: Actor, data: str) -> DialogWindowDto:
        async with self._uow:
            window = await self._dialog_repository.reset_to_snapshot(data)
        await publish_dialog_change(self._redis)
        return window

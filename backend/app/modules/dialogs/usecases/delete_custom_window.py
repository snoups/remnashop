from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._publish import publish_dialog_change
from app.modules.users import UserDto


class DeleteCustomDialogWindowUseCase(UseCase[str, None]):
    required_permission = Permission.DIALOGS_WINDOWS_DELETE

    def __init__(self, dialog_repository: DialogRepository, uow: UnitOfWork, redis: Redis) -> None:
        self._dialog_repository = dialog_repository
        self._uow = uow
        self._redis = redis

    async def _execute(self, actor: UserDto, data: str) -> None:
        async with self._uow:
            await self._dialog_repository.delete_custom_window(data)
        await publish_dialog_change(self._redis)

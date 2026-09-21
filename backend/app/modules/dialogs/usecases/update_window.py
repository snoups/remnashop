from dataclasses import dataclass
from typing import Optional

from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs.dto import DialogWindowDto, UpdateDialogWindowDto
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._publish import publish_dialog_change
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class UpdateDialogWindowInput:
    key: str
    banner_name: Optional[str] = None
    banner_name_provided: bool = False
    is_enabled: Optional[bool] = None


class UpdateDialogWindowUseCase(UseCase[UpdateDialogWindowInput, DialogWindowDto]):
    required_permission = Permission.DIALOGS_WINDOWS_UPDATE

    def __init__(self, dialog_repository: DialogRepository, uow: UnitOfWork, redis: Redis) -> None:
        self._dialog_repository = dialog_repository
        self._uow = uow
        self._redis = redis

    async def _execute(self, actor: UserDto, data: UpdateDialogWindowInput) -> DialogWindowDto:
        async with self._uow:
            window = await self._dialog_repository.update_window(
                data.key,
                UpdateDialogWindowDto(
                    banner_name=data.banner_name,
                    banner_name_provided=data.banner_name_provided,
                    is_enabled=data.is_enabled,
                ),
            )
        await publish_dialog_change(self._redis)
        return window

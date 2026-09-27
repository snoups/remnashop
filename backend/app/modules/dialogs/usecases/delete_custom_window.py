from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners import BannerRepository
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._banners import drop_window_banners
from app.modules.dialogs.usecases._publish import publish_dialog_change
from app.modules.users import UserDto


class DeleteCustomDialogWindowUseCase(UseCase[str, None]):
    required_permission = Permission.DIALOGS_WINDOWS_DELETE

    def __init__(
        self,
        dialog_repository: DialogRepository,
        banner_repository: BannerRepository,
        config: AppConfig,
        uow: UnitOfWork,
        redis: Redis,
    ) -> None:
        self._dialog_repository = dialog_repository
        self._banner_repository = banner_repository
        self._config = config
        self._uow = uow
        self._redis = redis

    async def _execute(self, actor: UserDto, data: str) -> None:
        async with self._uow:
            await self._dialog_repository.delete_custom_window(data)
            await drop_window_banners(self._banner_repository, self._config, data)
        await publish_dialog_change(self._redis)

from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import WINDOW_BANNER_PREFIX
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners import BannerRepository, delete_banner_file
from app.modules.dialogs.repository import DialogRepository
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
            # The window's own banner is named after its key and nothing else
            # references it, so it dies with the window instead of lingering.
            orphaned = await self._banner_repository.delete_all_named(
                f"{WINDOW_BANNER_PREFIX}{data}"
            )

        for banner in orphaned:
            delete_banner_file(self._config.media_dir, banner.name, banner.locale, banner.extension)
        await publish_dialog_change(self._redis)

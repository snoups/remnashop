from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners.repository import BannerRepository
from app.modules.banners.seed import restore_default_banner
from app.modules.users import UserDto


class RestoreDefaultBannerUseCase(UseCase[None, None]):
    """Puts the picture shipped with the project back as the shared banner --
    the shared one is replaceable, so it needs a way home."""

    required_permission = Permission.BANNERS_RESTORE_DEFAULT

    def __init__(
        self, banner_repository: BannerRepository, config: AppConfig, uow: UnitOfWork
    ) -> None:
        self._banner_repository = banner_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> None:
        async with self._uow:
            await restore_default_banner(self._banner_repository, self._config)

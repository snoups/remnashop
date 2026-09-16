from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners.dto import BannerListDto
from app.modules.banners.repository import BannerRepository
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto


class ListBannersUseCase(UseCase[None, BannerListDto]):
    required_permission = Permission.BANNERS_VIEW

    def __init__(
        self,
        banner_repository: BannerRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
    ) -> None:
        self._banner_repository = banner_repository
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> BannerListDto:
        async with self._uow:
            banners = await self._banner_repository.list_all()
            available_locales = await self._settings_repository.list_active_locales()
            return BannerListDto(banners=banners, available_locales=available_locales)
